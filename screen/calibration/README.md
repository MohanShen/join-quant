# screen/calibration/ — the screener's held-out set

104 JoinQuant community posts whose strategies have a **known** frozen-harness outcome:
23 pass / 81 fail, base rate **22.1%**.

| file | what it is |
|---|---|
| `posts.json` | what a screener sees: `ref`, title, tags, likes/clones/views/replies, body (≤2500 chars). **No outcomes.** |
| `answers.sealed.json` | the sealed key: `gate`, `objective`, `annual`, `sharpe` per ref |
| `epoch1-reference-predictions.json` | the epoch-1 blind run, for regression comparison |

## Rules

1. **A screener under evaluation must never read `answers.sealed.json`.** It is committed so the
   set is durable and re-runnable, not so it can be consulted. Grade by handing a screener
   `posts.json` alone — ideally in a fresh subagent with no prior context, which is how the
   epoch-1 numbers were produced.
2. Run it whenever `screen/screen.md` changes (see that file §7/§8). A rubric edit that lowers
   AUC is a regression.
3. **It grades pass-likelihood (axis S) only.** There is no ground truth for marginal
   information (axis M), which is the rubric's primary axis. A high AUC says the screener reads
   the market well; it does not say it is selecting the right posts. Guard M separately.

```bash
node utils/screen-score.js screen/calibration/epoch1-reference-predictions.json
```

## Provenance

Built 2026-09-17 by joining `harness/normalize-train.tsv` (status `normalized`) to
`data/discovered.json` metadata and fetching each body via `community/post/detailV2`.
Order is shuffled with a fixed seed so position carries no signal. Seven posts have no
retrievable body (two of them passes) — that handicap is deliberate and representative.
