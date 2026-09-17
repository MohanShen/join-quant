---
name: run-screen
description: Screen JoinQuant community posts for what is worth fetching and backtesting, using the frozen rubric in screen/screen.md. Runs the deterministic hard-reject prefilter, dispatches batches to the post-screener agent, merges banded verdicts into screen/verdicts.json, and reorders the fetch queue by priority. Emphasises MARGINAL information over pass-likelihood. Use when asked to screen posts, decide what to fetch next, prioritise the discovery queue, or find the most valuable community posts.
---

# Run the post screener

Decides **what deserves the 60 backtest-minutes/day** before any of them are spent. You are the
orchestrator: run the deterministic filter, dispatch judgement in batches, merge the verdicts.

**Authority**: `screen/screen.md` (frozen rubric, read-only). `harness/harness.md` for what the
backtest actually does. This skill is the entry point and does not restate the rubric.

## Why this exists

Ranking by popularity selects for redundancy. Measured on this corpus: the four most-cloned
posts all fail the gate, 57% of all gate-passes are 小市值 variants of a family that already has
35 members, and 16% of everything fetched is a byte-identical duplicate. The rubric's primary
axis is therefore **marginal information**, not pass-likelihood.

## Steps

1. **Prefilter (no tokens).**
   ```bash
   node utils/screen-prefilter.js --stats          # see the rejection breakdown first
   node utils/screen-prefilter.js --limit 200      # writes screen/candidates.json, with bodies
   ```
   Bodies are free and are what lifts screening from 0.75 to 0.90 AUC. Only use `--no-bodies`
   if the CDP browser is down.

2. **Dispatch in batches of ~40 posts** to the `post-screener` agent (`Agent` tool,
   `subagent_type: "post-screener"`). Give each batch: the slice of `screen/candidates.json` it
   owns, the `heldFamilies` map, and the output path to write. Batches are independent — send
   several in one message so they run concurrently.

3. **Merge** each batch's JSON into `screen/verdicts.json`, keyed by `ref`. Verdicts are sealed
   to the rubric epoch they were made under; record `rubric: "screen/screen.md epoch <n>"`.

4. **Check the concentration guard.** If any single family is more than half of the `fetch-now`
   band, stop and report it. Rubric §7: that is a rubric failure regardless of how good the
   scores look, because it means M is not doing its job.

5. **Reorder the queue.** Rewrite `data/copy-queue.json` so `fetch-now` then `fetch` lead,
   ordered by `priority`. `hold` stays in the store but out of the queue; `drop` is recorded in
   `screen/verdicts.json` so it is never re-screened.

6. **Report**: band histogram, top 10 by priority with their `mechanism` and `why`, any NEW:
   family proposals, and the concentration check.

## Validating a rubric change

Never edit `screen/screen.md` without re-running the held-out set:

```bash
node utils/screen-score.js <predictions.json>     # precision@K + AUC vs the sealed key
```

Epoch-1 reference: blind judgement scored **100% / 90% / 80%** at top-5/10/20 and **0.90 AUC**,
against 0.66 for popularity and 0.75 for a bare 小市值 keyword. A change that lowers AUC is a
regression. The set grades **axis S only** — it cannot validate M, so keep the step-4 guard.

## Do not

- Screen with judgement anything the prefilter already rejected — the answer is known.
- Let a high S pull M up. That is how the queue fills with variants you already hold.
- Treat a gate-pass as a win: the top-objective strategy in the corpus is unrealizable, which
  is what the rubric's R veto is for.
- Read `screen/calibration/answers.sealed.json` while screening.
