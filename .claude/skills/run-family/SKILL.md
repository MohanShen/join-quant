---
name: run-family
description: The merged research loop for ONE strategy family — understand it and improve it in a single queue, then finalize once on VAL. Replaces /run-study + /run-enhance.
---

# Run the research loop on one family

`/run-study` asked *why does this work*. `/run-enhance` asked *can it be better*. They were the
same machine — generator → gatekeeper → enclosed executor → recorder, both writing §2 of the same
family page, both calling the same executor on the same frozen bench. This is that machine, once.

**Authority**: `harness/harness.md` (frozen bench, read-only), `docs/wiki-schema.md` §2.3 + §3.3,
`docs/study-schema.md` §10, `docs/proposals/merged-research-loop.md`. This skill is the entry
point and does not restate them.

## The one principle

**无选择压力 is scoped to the IDEA TYPE, not to the pipeline** (`study-schema.md` §10):

| | `understand` | `improve` |
|---|---|---|
| a negative result is | **a finding** — recorded, equal to a positive one | a failed iteration |
| but a rejected variant is | — | **still recorded**, `判定: rejected`, one line |
| what it produces | understanding | a candidate |

Get this backwards and you lose the library's best material. ETF溢价's entire improve round rests
on q-1 and q-2, which are both **negative** results. An "did it improve?" gate in front of those
discards them.

## Read before proposing anything — not optional

```bash
node utils/research-queue.js <family>          # edges, queue, findings, implications, rejected §2
node utils/research-queue.js <family> --lint   # contract violations
```

`context()` returns what has already been tried, what each result *implied*, which directions are
**closed**, and which §2 variants were measured and rejected. An agent that has called it cannot
claim it did not know. Skipping this is how a round re-proposes finished work — ETF动量's idea-1
flagged *itself* as 新颖度为零, a re-measurement of a config the family already held.

Also read the family page: §1 (base), `edge:` (why it earns), §2 (variants), §4 (gaps), §6 (log).

## The loop

```
   ┌── generator A: understand ──┐
   │   (why does it work; what    │
   │    does each component do)   ├──► gatekeeper ──► queue ──► executor ──► recorder ──┐
   │                              │    (falsifiable?   (one     (frozen      (finding +  │
   └── generator B: improve ──────┘     worth it?      queue,    bench,       IMPLICATION │
       (within-family / cross-family     rank)         both      TRAIN)       + §2 row)   │
        borrow / new-family combo)                     kinds)                             │
                                                                                          │
   both queues empty ──► finalize ONCE on VAL ──► done ◄──────────────────────────────────┘
```

1. **Generate.** Both generators propose into one queue with `kind: understand|improve`. Every
   entry carries `from: [...]` — the prior results that prompted it. An empty `from` is allowed
   but **ungrounded**, and ranks last.
2. **Gate + rank.** Falsifiable? Answerable by one experiment? Worth the minutes? Rank, dispatch
   the top entry.
3. **Execute** on the frozen bench, `--window train`, one backtest at a time.
4. **Record** — the step that makes this a loop, see below.
5. **Repeat** until both kinds are exhausted, then VAL **once**.

## Recording: the finding is half the job

```bash
node -e "require('./utils/research-queue').recordFinding('<family>', {...})"
```

- `finding` = **what happened**. "sharpe 8.44 → 3.16 → 1.10 as the floor rises."
- `implication` = **what it changes about what we do next**. It must either
  - **close** a direction — "no_buy_after_day is monotone-worsening from 2; that knob is closed", or
  - **open** one — "the 2e6 floor is too loose; retest every member at 1e7 before trusting any Δ".
  A restatement of `finding` is refused by the contract.
- `spawned` = the idea ids this produced, or `none`.
- `edgeRef` = which edge claim it bears on. **A result that refutes an edge claim must flip that
  claim's `status` to `refuted` in the same write.**

Then the §2 row on the family page: `类型` (understand|improve|raw) and `判定`
(adopted|rejected|informative). A `rejected` row gets **one line** — ETF动量's §2 averages 3.6KB
per row, which is why failures need a short form, not exclusion.

## `edge:` — what makes this family earn

Every family should answer: **what is intrinsically predictive here?** 小市值 → the size factor.
Some → an arbitrage. Some → one genuinely predictive feature. One or more, each fundamental.

- Vocabulary and the block's shape: `wiki-schema.md` §2.3. `test:` is **mandatory** — a claim with
  no stated refutation is not a claim.
- `status: proposed` carries **no authority** and may not be cited as fact. Promoting to `measured`
  costs one experiment: run the `test:`.
- `kind: none-found` is legal and valuable — a family nobody can name an edge for is a fitting
  artifact until shown otherwise. It is **flagged, not deprecated**.
- A measured edge becomes the improve-generator's **prior**: if the edge is size, tightening the
  size threshold is on-mechanism; bolting on an unrelated momentum filter is off-mechanism and is
  how you overfit. `--lint` flags an improve idea that names no `edgeRef` once an edge is measured.

## Finalizing — read this before touching VAL

**One validation per (family, epoch).** `utils/val-budget.js`, enforced in the executor.

```bash
node utils/val-budget.js <family>      # free, check before you build the candidate
node utils/strategy-post-backtest.js <cand>.py "<expId>" --window val --family <family> --usage-limit <N>
```

`--family` is **required** on VAL — an unnamed VAL is an untracked VAL. If the budget is spent,
**do not look for a way around it**: a different candidate does not buy a second validation,
because "the last VAL disappointed so make a new candidate" is selection on VAL one run at a time.
Report back and keep iterating on TRAIN. Never set `JQ_ALLOW_REVAL` — that is the human's switch,
like `JQ_ALLOW_OOS`.

## Do not

- Put an improvement gate in front of an `understand` experiment.
- Discard a measured `improve` variant without a §2 row — code reverts, understanding does not.
- Run two backtests at once. The completion signal is the account-wide running count; concurrent
  runs have returned identical metrics for different strategies. The executor refuses with
  `CONCURRENT-STOP`; do not set `JQ_ALLOW_CONCURRENT`.
- Touch the reserved OOS window. Read the boundary from `node utils/harness-config.js` rather than
  assuming one — it moves with the epoch.
- Cite a `proposed` edge as a fact, or write an edge claim you cannot state a test for.
