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

## Scope: ONE family, then stop

`/run-family <family>` works a **single** family and **ends when that family is done**. It does
not walk a queue — the daily pipeline picks the next one and invokes again. One family per
invocation is what makes the run resumable and the budget attributable.

Pick the family from `node utils/family-queue.js` (highest score first) unless the human named one.

### Step 0 — the early exit, before anything else

`family-queue` reports a `reason`. **If it is `new-members`, do this first:**

1. Read the new members' normalized results and `node utils/research-queue.js <family>`.
2. Ask one question: **do the new variants raise an idea that has not already been explored?**
   Compare against prior findings' implications, `closedDirections`, and §2 rows already
   `rejected`.
   ⚠ `closedDirections` now means "closed on THIS bench". `context().staleClosures` are closures
   made on a bench the active epoch rejects — 125 of 134 at epoch 9 — and they do **not** make an
   idea a duplicate. If the only thing standing between a new member and a live idea is a stale
   closure, that is an idea, not an early exit. Judge the reasoning (mechanism survives a bench
   change, a level or window argument does not), rank, and cite the stale qId in `from`.
3. **If not — log the new members' normalized results as §2 rows (`类型: raw`, `判定: —`), record
   a `research` consumption event with outcome `logged-only`, and EXIT.** Do not open the loop.
   A new member of a family you have already dissected is usually one more variant of a settled
   mechanism; spending a day's budget to rediscover that is the single easiest way to waste it.
4. If yes — say which idea and why it is new, then enter the loop with that idea already queued.

`reason: never-researched` skips step 0 and goes straight to the loop.

### Step 0b — `reason: integrate-blocked` is a NARROW job, not a round

The family is researched; it is stuck at the **exit gate** on a step only this loop performs, and
the queue's `note` is the gate's own sentence (`node utils/integrate-eligible.js <family>` prints
it with its owner). This reason only ever appears when that owner is `research`, so the work is
bounded and almost always one of three things:

| gate says | do this |
|---|---|
| `never validated` | finalize the existing champion on VAL — **one** run. The selection is already made; do not re-open TRAIN to look for a better candidate first |
| `no realizability:` / `realizabilityScope` mismatch | score it with evidence and write `realizability:` (+ `realizabilityScope:` when the candidate is a shelf product). **Costs no backtest** |
| `no universe:` | fill the field from §1. Free |

**Do the named step, record it, and EXIT.** Do not enter the generator loop: the family was
already worked to a stop, and a reopened round would re-buy findings it holds. Then re-run
`node utils/integrate-eligible.js <family>` and report whether it now reads `eligible` — that,
not a clean exit, is what says the block is gone.

⚠ If the gate's sentence names something you cannot clear (a VAL budget that is spent, a VAL that
validated a different book), **stop and report it**. Those are owned by `human`, so they should
never have reached you; never set `JQ_ALLOW_REVAL` to get past one.

#### ⚠⚠ If the right answer is NOT to do the step, RECORD that — or tomorrow re-dispatches

`never validated` is a *to-do only if the family has a candidate worth its one validation*. Often
it does not, and the honest answer is that **BLOCKED is the correct terminal state, not a task**.
Measured 2026-10-17: the first four families this reason reopened had **all four** already decided
exactly that, each with the reason in §4 — and the dispatch was about to tell a session to
"finalize on VAL" anyway. Nothing was spent, but only because it was caught mid-run.

So if you conclude the validation should not be spent, write the decision into the family page
frontmatter and exit. The gate then reports `owner: none` and the planner stops reopening it:

```yaml
valDeclined: 8                      # the epoch you decided under (provenance)
valDeclinedBasis: "why — REQUIRED, and name the clearing condition"
```

- **A basis is required.** The next round must read *why*, not merely *that*. Quote your own §4
  finding rather than paraphrasing it.
- **Name what would change your mind** — "a built candidate not dominated by member X", "a
  point-in-time pool truncated to its own N". Three of the four real cases state one.
- **It does not expire on an epoch bump**, because most such reasons are about the DATA (a
  hindsight-selected pool, a VAL window inside the author's own sample) and do not change when
  fills and fees do. What reopens the family is a **new member**, which can change the champion —
  that path does not consult this field.
- You do **not** need to declare it when your candidate simply fails the 1.5 gate: the gate
  derives that case on its own and already reports `owner: none`.

### Stopping and resuming

The run stops when the family is done **or** the budget runs out. Either way the state is on disk
and the next invocation continues: `study/<family>/queue.json` (ideas with their status),
`findings.tsv` (what has been answered), and the family page §2/§6. Nothing needed for resumption
lives only in the session — report where you stopped and what is still `queued`.

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
          (generators run CONCURRENTLY; exactly ONE executor at a time, ever)
```

### You are the ORCHESTRATOR. Dispatch the five roles; do not play them.

Each role is an `Agent`-tool subagent with its own contract in `.claude/agents/`. They are
**ephemeral** — spawned for one task, returning concisely, never messaging each other. The handoff
between them is **on disk** (`study/<family>/queue.json`, `findings.tsv`, the family page), which
is why a round survives a budget stop.

⚠ Until 2026-10-17 this skill described the five roles in the diagram above but never told you to
dispatch them, so a session played all five itself and the five contracts sat unreferenced. The
diagram was read as a phase description. It is a dispatch spec.

| # | subagent_type | when | may write |
|---|---|---|---|
| 1 | `family-understand` | generate, if the understand kind is not exhausted | nothing (read-only) |
| 2 | `family-improve` | generate, if the improve kind is not exhausted | nothing (read-only) |
| 3 | `family-gatekeeper` | after either generator returns ideas | `study/<family>/queue.json` |
| 4 | `family-executor` | one dispatched idea, **one at a time, never parallel** | the variant `.py` |
| 5 | `family-recorder` | after every completed execution | `findings.tsv`, §2/§6, the KB |

**Dispatch 1 and 2 in the same message** when both kinds are live — they only read, so they run
concurrently and that is the one safe fan-out in this loop. Give each the family name and point it
at `node utils/research-queue.js <family>`; it reads its own context, you do not paste it in.

**Never dispatch two `family-executor`s at once.** The completion signal is the account-wide
running count, concurrent runs have returned identical metrics for different strategies, and the
executor refuses with `CONCURRENT-STOP`. One executor, foreground, then the recorder.

Then loop: gatekeeper → executor → recorder → back to the gatekeeper, generating again only when
the queue runs dry. Stop when both kinds are exhausted or the budget is gone.

### What stays YOURS and is never delegated

| yours | why |
|---|---|
| the **loop control** and when to stop | a subagent cannot see the budget or the other roles |
| the **backtest budget** (`--usage-limit`), and that only one executor runs | account-wide, and a subagent cannot observe it |
| **VAL** — whether to spend the family's one validation, and the `--family` flag | one per (family, epoch), irreversible |
| **`valDeclined:`** — deciding the VAL should NOT be spent, and recording it | a decision about the family, not about one experiment |
| the **report** at the end | only you saw the whole round |

⚠ **Do not let the executor finalize on VAL.** Its contract is TRAIN deltas; it returns
`VAL-BLOCKED` as a failure kind precisely because the decision is not its. The recorder writes
findings, not validations.

⚠ **A subagent's return is a report, not a result.** The executor hands you a delta; the ledger
and the stored curve are what make it true. If a returned number and the ledger disagree, the
ledger wins — and say so rather than passing the report through.

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

**Before you stop — for any reason, including running out of budget — run:**

```bash
node utils/research-sync.js <family>      # findings.tsv -> §6, append-only, idempotent
```

`findings.tsv` is **gitignored**; §6 is the durable copy. Measured: a round killed mid-loop by an
API 529 left **4 findings in the ledger, 0 rows in §2 and no §6 at all** — results that existed
only in a file git does not track. The sync is what makes an interrupted round survive, and it is
safe to run at any point.

Then the §2 row on the family page: `类型` (understand|improve|raw) and `判定`
(adopted|rejected|informative). A `rejected` row gets **one line** — ETF动量's §2 averages 3.6KB
per row, which is why failures need a short form, not exclusion.

## `edge:` — drafted early, settled late

The edge is **not** a one-off pass. It is a stage of this loop, at both ends:

- **Draft it first.** Before the first experiment, write the family's `edge:` block from what is
  already on the page (§1 mechanism, §6 log) at `status: proposed`, with its `test:`. This is
  cheap, costs no backtest, and it is what gives the improve generator a prior to steer by from
  the very first idea.
- **Revise it last.** When the loop is done, come back to the block with everything the round
  measured. A result that ran the `test:` promotes it to `measured`; a result that contradicts it
  flips it to `refuted` — **in the same write as the finding**. A refuted claim left reading
  `proposed` will be cited by the next round as a prior it no longer deserves.
- In between, any finding that bears on it sets `edgeRef` so the link is traceable.

The draft is a hypothesis, not a conclusion: `proposed` carries no authority, may not be cited as
fact, and is excluded from `utils/edge-redundancy.js`. Promoting it is what costs an experiment.

The question it answers: **what is intrinsically predictive here?** 小市值 → the size factor.
Some families → an arbitrage. Some → one genuinely predictive feature. One or more, each
fundamental — "uses a 5-day moving average" is a technique, not an edge. Vocabulary and block
shape: `wiki-schema.md` §2.3; `test:` is mandatory.
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

⚠ And do not reach OOS from this loop. Since 2026-10-16 `--allow-oos` is a plain CLI flag, so the
executor will not refuse an OOS run on its own — passing it is the whole barrier. OOS belongs to
`/run-oos`, which pre-flights readiness and charges the budget.

## After a VAL completes: ARCHIVE the validated book

⚠⚠ The loop is not finished when VAL returns. `integrate-eligible` takes a family's CANDIDATE from
the product shelf (`validated_strategies/`), so **a family whose product never reaches the shelf
can never supply one** — it falls back to the best ingested ledger member, which is usually not the
book the VAL validated, and the family reads `blocked` forever.

The `family-recorder` contract owns the step and its header format. It was lost when
`/run-study` + `/run-enhance` merged into this loop, which is why the shelf's existing artifacts
were each archived by a one-off `study/<family>/archive*.js`.

## The EXIT GATE — what this loop has to deliver for the next phase

⚠ **Finishing the loop is not the same as producing a candidate.** Integration takes only the best
variant that ALSO cleared validation, and it will not take an untradeable one (user specification,
2026-10-16). `node utils/integrate-eligible.js <family>` is the check; three things must hold:

| requirement | why |
|---|---|
| a **champion** measured under an epoch the active one accepts | a result on a superseded bench is history |
| a **VAL that PASSED** `stageGate('validate')` | integration may not be handed a TRAIN-only number |
| **`realizability:` ≥ 2** on the family page | nothing whose fills a daily bar cannot honour may enter the set a universe ships |

So **scoring realizability is part of this loop's job**, not integration's. Write `realizability:`
and `realizabilityBasis:` into the family page frontmatter, with the evidence behind the number —
1 means fills a daily bar cannot honour.

⚠ **Unknown BLOCKS, it does not permit.** A family with no `realizability:` is reported blocked
rather than assumed fine, the same rule the VAL budget applies to an unknown epoch. ⚠ And it is
**not** inferable from the `不可实现` regex: 打板短线 does not match it and was still scored 1 on
evidence — it buys the next-day open of yesterday's 涨停, and a sealed 一字板 cannot be bought at
any price.

⚠ **Order matters downstream.** Families enter this loop ordered by **champion TRAIN sharpe**,
highest first (`utils/family-queue.js`), because integration is incremental: the first family to
clear this gate in a universe becomes what every later arrival must beat.

## Do not

- **Play one of the five roles yourself.** You are the orchestrator: dispatch
  `family-understand` / `family-improve` / `family-gatekeeper` / `family-executor` /
  `family-recorder` and keep the budget, the VAL decision and the loop control. A session that
  does the reading, the experiment and the write-up itself is what this skill looked like before
  2026-10-17, and it left five written contracts unused.
- **Run two `family-executor`s at once**, or dispatch one while another is in flight. One backtest
  at a time, account-wide.
- **Delegate VAL**, or let a subagent set `--window val`. One validation per (family, epoch) is
  yours to spend or to decline (`valDeclined:`).
- Pass a subagent's returned number through as a result without the ledger agreeing.
- Put an improvement gate in front of an `understand` experiment.
- Discard a measured `improve` variant without a §2 row — code reverts, understanding does not.
- Run two backtests at once. The completion signal is the account-wide running count; concurrent
  runs have returned identical metrics for different strategies. The executor refuses with
  `CONCURRENT-STOP`; do not set `JQ_ALLOW_CONCURRENT`.
- Touch the reserved OOS window. Read the boundary from `node utils/harness-config.js` rather than
  assuming one — it moves with the epoch.
- Cite a `proposed` edge as a fact, or write an edge claim you cannot state a test for.
