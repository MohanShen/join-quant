---
name: run-daily
description: Run one day of the join-quant pipeline — pick the stage by queue priority (enhance > study > normalize > discover), spend the backtest budget on it, chain to the next stage while minutes remain, write a dated markdown summary to docs/daily/, and commit and push it. Use when asked to run the daily pipeline, move strategies forward, drain the queues, or decide what today's backtest budget should be spent on.
---

# Run one day of the pipeline

The orchestration layer above `/run-study`, `/run-enhance` and the normalizer. It does not
decide *how* to study or enhance — it decides **which stage gets today's 60 backtest-minutes**,
runs it, reads what came back, and moves on.

**Authority**: `utils/daily-pipeline.js` owns the decision. `harness/harness.md` is the frozen
bench. This skill is the entry point and the judgement layer, not a second planner.

## Division of labour — read this before overriding anything

**Stage selection is arithmetic, and it is already written.** `plan()` compares four queue
depths against a fixed priority. There is one right answer and it costs no tokens to compute:

```bash
node utils/daily-pipeline.js --plan      # decide and explain, run nothing
```

Do **not** re-derive the pick by reading the queues yourself and reasoning about it. That
replaces a tested function with a guess, and the cost of guessing wrong is a whole day's
budget spent on the wrong stage. Your job starts where the arithmetic runs out.

**What actually needs judgement** — the cases the planner cannot resolve:
- a stage returns `blocked` for a reason no cron can fix (a stale session pin, a missing
  branch) → diagnose it and say what the human must do;
- an agent loop finishes but its own ledger shows nothing moved → that is a silent no-op, not
  a success; find out why before letting the chain continue;
- a stage errors in a way the log does not explain;
- the queues say one thing and the artefacts say another (see the manifest trap below).

## Steps

1. **Plan.** `node utils/daily-pipeline.js --plan`. Report the four queue depths and the pick.
2. **Check the board is honest.** `node utils/daily-pipeline.js --sync-manifest --dry`.
   ⚠ The planner and the study agent read *different* queues — the planner derives staleness
   from `data/consumption.tsv` (member-aware), the agent is told to work `study/manifest.json`.
   These disagreed: the manifest called all 14 families `done` while the ledger called all 14
   stale, so a dispatch would have found nothing to do and still exited 0. The ledger wins;
   the sync reopens what it calls stale. Run it without `--dry` before dispatching study.
3. **Run.** `node utils/daily-pipeline.js` chains stages while budget remains, re-planning
   between each. `--once` for a single stage, `--stage <name>` to override the first pick.
4. **Read what came back.** Every stage records to `data/daily-state.json`. For an agent loop,
   do not take exit 0 as proof of work — check that its ledger moved (`enhance/results.tsv`,
   the family page's §2/§6, or a new `consumption.tsv` event).
5. **Close the day: write the summary, commit, push.**

   ```bash
   node utils/daily-summary.js --commit       # write docs/daily/<YYYY-MM-DD>.md, commit, push
   node utils/daily-summary.js --dry          # preview it, write nothing
   ```

   `node utils/daily-pipeline.js` already does this at the end of a run (`--no-commit` writes
   without pushing, `--no-summary` skips it). Run it by hand when you drove the stages yourself.

   The summary leads with **what moved**, not what ran — artefact delta first, stage table
   second. That ordering is deliberate: "enhance → ran" is the exact line all three of this
   repo's silent-no-op failures produced. If it says **NO-OP**, say so in your report rather
   than describing the run as fine because the command succeeded.

   ⚠ The commit stages `git add -u` plus an enumerated allowlist of paths a run legitimately
   creates (`SAFE_ADD` in `daily-summary.js`). Never `git add -A` — that once committed a git
   worktree as a gitlink. Anything untracked outside the allowlist is listed in the summary
   under "Untracked and NOT committed" and left for a human; if you see entries there, decide
   whether they belong in the allowlist rather than adding them ad hoc.

6. **Report**: stage(s) run, minutes spent, what moved, what is blocked and who must unblock it,
   and the path of the summary you wrote.

## The failure mode this exists to catch

A daily job that exits 0 while doing nothing is worse than one that fails, because nobody
looks. Three live examples from this repo, all of which returned success:

- `autoenhance-loop.sh` required an `enhance/*` branch that no longer existed → every fire
  logged "skip" and exited 0;
- the enhance session pin pointed at `research/jul12`, a branch that does not exist at all;
- `study/manifest.json` said every family was `done` while the consumption ledger said every
  family was stale.

So: **`blocked` is reported, never swallowed, and the planner exits non-zero on it.** If you
find yourself about to describe a run as fine because the command succeeded, check the ledger
instead.

## Budget

60 free backtest-minutes a day, shared with every other JQ consumer through
`data/jq-pipeline.lock`. This pipeline caps each backtest at **30 minutes** (`--max-poll-min`,
default is 20) and passes `--usage-limit 55` to stay inside the free tier.

A strategy that blows the cap is **deferred, not discarded**: `data/deferred.json` holds it and
re-offers it only at a *higher* cap, because re-running at the same cap spends the same minutes
to learn the same thing. `slow-skipped` stays terminal in the normalizer itself — making it
retriable re-bills it every batch.

## Do not

- Re-derive the stage pick by hand; call `--plan`.
- Treat a clean exit code from an agent loop as evidence that work happened.
- Cold-start a study/enhance session. The loops **resume** a human-pinned session
  (`scripts/auto{study,enhance}-interactive.sh`) so the agents keep context; a fresh session
  per stage loses it and re-reads the KB.
- Touch the OOS window, or `--force` any wiki builder.
- Sweep untracked files in with `git add -A` — the commit allowlist is enumerated on purpose.
