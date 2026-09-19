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
   node utils/screen-prefilter.js --stats                       # rejection breakdown first
   node utils/screen-prefilter.js --cates 14,3                  # 精华 + 文章; 问答 deferred
   node utils/screen-prefilter.js --limit 200 --sample 42       # representative slice, not crawl order
   node utils/screen-prefilter.js --keys <file.json>            # screen ALREADY-FETCHED posts
   ```
   - `--cates 14,3` first. Measured: 问答 (cate=10) screens at **94% drop** vs 24–30% for
     文章/精华 — help-desk posts attach a backtest in order to ask about it, so no payload rule
     catches them. Q&A is deferred, never rejected (it still produced usable ideas).
   - `--sample <seed>` for a bounded batch: plain `--limit` takes crawl order, which front-loads
     the old popularity-ranked posts.
   - `--keys` bypasses R3 (already fetched) for a named set. R3 answers "should we download
     this"; it is the wrong rule for "which file we already hold deserves backtest minutes".
   - Bodies are cached (`utils/post-cache.js`), so re-running costs nothing for posts seen before.
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

6. **Hand off to normalization.** The fetch queue is only half the job: for posts whose source
   we ALREADY hold, `node utils/normalize-backfill.js` turns verdicts into
   `data/pending-normalize.json` in priority order (the daily normalizer drains it).
   It EXCLUDES `S=0` entries and DEFERS ones flagged multi-hour — both would spend the shared
   60 backtest-min/day on a guaranteed non-result.

7. **Report**: band histogram, top 10 by priority with their `mechanism` and `why`, any NEW:
   family proposals, and the concentration check.

## ⚠ The bands rank INFORMATION, not runnability
A `fetch-now` entry may be a write-up, futures-only, or need data outside 2022–23 — several top
picks score `S=0`. **Read `flags` before queueing anything for backtest minutes.** Splitting the
bands into read-value vs backtest-value is a candidate for a future rubric epoch; until then the
flags are the guard.

## What a full pass looked like (2026-09-18, epoch 1)
857 posts screened → fetch-now 52 / fetch 277 / hold 200 / drop 328, spanning 25 families with
the largest at 12%. The highest-value results were **falsifications of what we already hold**
(lookahead dissections, an overfit audit, a list of backtest cheats), not new strategies —
which is axis M behaving as designed. 93 `NEW:<mechanism>` families were proposed and **none is
registered yet**; registering them is what unblocks `/run-study` and `/run-enhance`.

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
