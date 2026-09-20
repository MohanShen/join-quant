# CLAUDE.md

## Overview

**join-quant** is an automated pipeline for the [JoinQuant](https://www.joinquant.com) Chinese quant platform. It discovers community strategies, clones their source + performance metrics, and runs backtests — both for community posts and for local custom strategy files. Node.js (>=18), Playwright for browser automation, raw HTTP for the API paths.

## Setup & Commands

```bash
npm install          # installs playwright
npm test             # node --test tests/*.test.js

# CLI (see index.js)
node index.js community <postId> <backtestId> [replyId]  # backtest a community post
node index.js custom <path-to-strategy.py>               # backtest a local file
node index.js custom --backtestId <id>                   # re-run existing backtest
node index.js list                                       # list local ./strategies/
node index.js login                                      # force fresh login, cache cookies
node index.js status                                     # show cached cookie status

# Pipeline 1 (discovery/clone) entry points — not wired into index.js
node utils/strategy-discover.js            # crawl community listV2, build queue
node utils/strategy-fetch.js [N]           # process clone queue (optional limit)
node utils/strategy-daily.js               # cron: discover -> clone loop
node utils/strategy-daily.js --discover-only

# Discovery knobs (Pipeline 1)
node utils/strategy-discover.js --pages 20            # walk 20 pages per (cate,type) combo
node utils/strategy-discover.js --pages 50 --limit 50 --cates 3,0
node utils/strategy-discover.js status                # strategy + resource queue status

# Research resources (community write-ups the strategy pipeline drops)
node utils/resource-fetch.js                          # drain the resource queue
node utils/resource-fetch.js 10 --kind notebook       # N of one kind
node utils/resource-fetch.js --dry

# Factor library (research input)
node utils/factorlib-ingest.js                        # zz500 / 3y, both cost levels
node utils/factorlib-ingest.js --universe zz1000 --range 1y
node utils/factorlib-ingest.js --list-settings        # legal universe/range/fee values

# 量化课堂 (137 lessons)
node utils/tutorial-ingest.js                         # catalog + all bodies
node utils/tutorial-ingest.js --catalog               # catalog only

# One-off: re-key the stores from postId to uniqueKey (idempotent, backs up)
node utils/migrate-unique-key.js --dry

# Screening — decide what deserves the 60 backtest-min/day (see screen/screen.md)
node utils/screen-prefilter.js --stats        # deterministic hard rejects, no tokens
node utils/screen-prefilter.js --limit 200    # + fetch bodies -> screen/candidates.json
node utils/screen-score.js <predictions.json> # grade a screener vs the sealed 104-post set
node utils/screen-prefilter.js --limit 200 --sample 42 --cates 14,3   # seeded, 精华+文章 first
node utils/screen-merge.js                    # validate batch verdicts -> screen/verdicts.json, rebuild queues
node -e "console.log(require('./utils/post-cache').size())"   # cached post bodies
node utils/normalize-backfill.js --dry        # queue held-but-unmeasured strategies by screening priority
node utils/normalize-sync.js                  # reconcile wiki pages + pending queue against the ledger
node utils/harness-config.js                  # print the active harness epoch
node utils/harness-config.js --verify         # check the frozen Python literals match it
node utils/consumption-report.js --next       # what each loop should take next
node utils/wiki-type-build.js --check         # family -> type assignment (universe x turnover)
node utils/wiki-concept-lint.js               # concept strategyCount drift
node utils/type-integrate-check.js <c.json>   # guard on a type-level integration candidate
node utils/strategy-normalize.js --window train --files "$(node -e "console.log(require('fs').readFileSync('data/pending-normalize.json','utf8').match(/[^\"\[\],\s]+\.py/g).join(','))")" --usage-limit 55
```

### Chrome / auth setup (required for Pipeline 2)

Pipeline 2 connects to an already-logged-in Chrome over CDP to inherit `httpOnly`
session cookies and bypass JoinQuant's CAPTCHA. **Where that Chrome runs is
configurable** — `config/exec.env` (gitignored; template at `config/exec.env.example`):

```bash
JQ_EXEC_MODE=local     # or: remote
```

**local mode** — Chrome on this machine. Start it once and keep it running:

```bash
nohup /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
  --remote-debugging-port=9225 \
  --user-data-dir=/tmp/jq-auth-browser \
  > /tmp/chrome-jq.log 2>&1 &
# First run: log into joinquant.com manually. Closing Chrome invalidates the session.
```

**remote mode** — Chrome runs on the Windows QMT server (see the `QMT-server` repo).
Its debug port is bound to the server's `127.0.0.1`, so an **SSH tunnel** bridges it:

```
localhost:9225  ->  ssh  ->  server 127.0.0.1:9225
```

The tunnel opens **automatically** — `utils/exec-config.js` probes the CDP endpoint on
every entry point and runs `scripts/cdp-tunnel.sh up` if nothing answers. Manual control:

```bash
./scripts/cdp-tunnel.sh up|down|status
```

Because the tunnel presents the browser at `localhost:9225`, every existing
`connectOverCDP('http://localhost:9225')` call works unchanged in both modes. This
also keeps Chrome's Host-header check happy (it rejects non-localhost `Host` values)
and avoids exposing the debug port — CDP on a logged-in brokerage session is a full
remote-control channel and must never be opened to the network.

In **remote mode the local-browser fallback is disabled**: the logged-in session lives
in the server's Chrome profile, so launching a browser on the Mac would only hit the
login page + CAPTCHA. `strategy-post-backtest.js` fails loudly instead.

Environment variables (optional — CDP path needs no credentials):
`JOINQUANT_USERNAME`, `JOINQUANT_PASSWORD`. `JQ_CDP_URL` still overrides the resolved
URL outright; `JQ_EXEC_MODE`, `JQ_CDP_PORT`, `JQ_REMOTE_SSH_HOST`, `JQ_REMOTE_SSH_OPTS`,
`JQ_REMOTE_CDP_PORT` override `config/exec.env` per-invocation.

## Two Pipelines

**Pipeline 1 — Daily Discovery & Clone** (`pipelines/community.js`, `utils/strategy-*.js`):
`GET /community/post/listV2` (paginated) lists community posts → split into **strategies**
(32-char `backtestId`) and **resources** (Jupyter `notebookPath`, `fileKey` attachment, or a
研报分享 / 研报复现 / 研究 tag) → dedupe against `data/discovered.json` + `data/resources.json`
→ for each strategy: `GET /algorithm/backtest/source` (Python source) +
`POST /algorithm/backtest/stats` (metrics) → save `.py` to `strategies/` → WeChat alert.
Both queues ranked by composite score (strategies: `likes + clones × 0.5`).

> ⚠ **All HTTP goes through `utils/jq-http.js`, never raw `https.get`/`curl`.** JoinQuant
> geo-blocks requests from outside mainland China with an **HTTP 200 HTML** page
> (「当前地区暂不支持访问」), so a raw call parses as a JSON error and older code read that
> as "no results" — Pipeline 1 died silently this way for two months. `jq-http` runs
> `fetch()` **inside the CDP Chrome** (right region + logged-in cookies), falls back to
> direct https only when CDP is down, and **throws** `GeoBlockedError` rather than
> returning an empty list. Never reintroduce a direct HTTP call to joinquant.com.

`listV2` pagination is deep: `page=800` at `limit=50` still returns a full page, reaching
back to 2019. Use `--pages N`; the crawler stops a combo after **5 consecutive** pages that add
nothing new. It used to stop after the *first* such page, which silently truncated sparse
categories — `cate=10` yielded 7 posts out of ~17,300 because its pages carry only 4–6
qualifying posts each, so one page of already-known items ended the sweep.

**`cate` = the forum's tabs** (read off the live site 2026-09-17; the tabs are disjoint and
`cate=0` is the superset):

| cate | tab | size | note |
|---|---|---|---|
| 0 | (none) | 60,000+ | superset; held 50/51 of `cate=3`'s page 1 |
| 3 | 文章 | ~42,300 | ordinary articles — the site default, and **the only slice the crawler used** |
| 10 | 问答 | ~17,300 | Q&A — where debunking and pitfall discussion lives |
| 13 | 公告 | small | platform announcements |
| 14 | 精华 | ~350 | editorially featured; page 1 was 50/50 `isBest`, median likes 125 vs 5 |

⚠ `strategy-discover.js` used to describe `cate=3` as 精华. **It is not** — 精华 is `cate=14`,
which had never been crawled.

**Pipeline 2 — Custom Strategy Backtest** (`pipelines/custom.js`, `backtest/runner.js`):
Browser-automated via CDP. Create `algorithmId` → inject Python into JQ's **Ace editor**
(`window.ace.edit(div).setValue(...)`, also synced to hidden `<textarea id="code">` which
the backend reads on save) → click 保存 / 编译运行 → **reload-poll** the buildList every 5s
for `完成` → scrape the result table for return/drawdown/Alpha/Beta/Sharpe.

> Why CDP, not a Playwright launch? JQ stores `PHPSESSID`/`token` as `httpOnly` cookies that
> Playwright can't set, and headless browsers hit the 拼图验证 CAPTCHA. CDP reuses the real session.
> Why reload-polling? JQ mutates backtest status in-place via XHR; a static `goto` misses updates.

## Layout

Only the directories whose contents aren't self-evident:

| Path | Purpose |
|------|---------|
| `harness/` | **Shared frozen backtest台**: `harness.md` (window/cost/OOS protocol, read-only) + `normalize-*.tsv` ledgers (gitignored). Used by study + enhance + future research. |
| `enhance/` | Auto-**enhance** team (optimize a strategy FAMILY): `program.md`, `candidates/`, `strategy_template.py`, transient `ideas-queue.json`/`loop-state.json`/`results.tsv` (gitignored) |
| `study/` | Auto-study team (understand a strategy FAMILY): `program.md`, `<family>/baseline.py` + `variants/`, transient `questions.json`/`findings.tsv` (gitignored). Writes back to `wiki/families/`. |
| `wiki/types/` | **Strategy TYPES** — generated by `utils/wiki-type-build.js`. A coordinate over families: universe (from the base source) x turnover band. Families sharing a type are integration candidates. Not a third page hierarchy; family and concept stay orthogonal. |
| `screen/` | **Frozen SCREENING rubric** — `screen.md` (four axes, priority formula, bands; read-only, epoch-versioned like `harness.md`) + `calibration/` (104 posts with sealed harness outcomes, the screener's held-out set). Decides what is worth fetching BEFORE backtest budget is spent. |
| `research/` | Reserved for a future auto-**research** pipeline — broad context: new data / factors / trading ideas. NOT the current optimize loop (that is `enhance/`). Holds `factorlib/` (below). |
| `research/factorlib/` | JQ **因子看板** ingested by `utils/factorlib-ingest.js`: 285 factors with formulas, IC/IR, quintile returns and turnover, pulled at **both** cost levels. `factors.tsv` + generated `README.md` (tracked); raw payloads in `data/factorlib/`. |
| `research/tutorials/` | **量化课堂**, 137 lessons in 5 categories, ingested by `utils/tutorial-ingest.js` via `detailV2` (free). Category 新手专区 is a full factor-research methodology chain. |
| `resources/` | **Raw layer #2** (alongside `strategies/`): community RESEARCH write-ups as `.md`, fetched by `utils/resource-fetch.js`. One file per post, frontmatter + full body. Notebook/attachment availability is recorded but the notebook itself is **not** downloadable (see Notes). |
| `validated_strategies/` | Finalized strategies that completed VAL (Agent 4 archives here; **tracked** = product shelf) |
| `data/` | **Tracked** (private backup) — discovery + resource state, `factorlib/` raw payloads. Only `data/cookies.json` is gitignored. |
| `auth/` | Session cookies; `auth/cookies.json` itself is **gitignored** (default cookie path). |

## Notes & Gotchas

- `data/` and `auth/` are **tracked** (private backup); only `data/cookies.json` and
  `auth/cookies.json` are gitignored. Never commit a cookie file.
- Default cookie path in `index.js` is `auth/cookies.json`.
- **Never call joinquant.com with raw `https`/`curl`** — use `utils/jq-http.js`. See the
  geo-block note under Pipeline 1.
- ⚠⚠ **JoinQuant re-mints IDs on every request.** `postId`, `backtestId`, the factor
  dashboard's `factor_id` and the tutorial list's `studyId` are all regenerated per call —
  the same object comes back under a new id each time, and old ids still dereference, so
  nothing fails loudly. **Stable handles**: community post = `uniqueKey`; factor = `name`;
  tutorial lesson = `title`. Never key a store, a dedup or a join on an id.
  This is why `data/discovered.json` was 10% duplicates and the `copied` map never matched
  (fixed by `utils/migrate-unique-key.js`; `postKey()` in strategy-discover.js is the rule).
- Community **notebooks cannot be downloaded** — the post page only offers 克隆研究, which
  copies into your research environment and **spends 积分 (credits)**; stored `notebookReport`
  paths 302 to 404 on old posts. `resource-fetch.js` saves the free prose and records the
  notebook as unavailable. The account currently holds **2 credits** and no VIP.
- The factor dashboard defaults to `commisionFee=0` (no costs), the same blind spot as
  `harness.md` §2. At `commisionFee=18` only **6 of 285** factors keep a positive excess
  annual return, down from 23 — and every survivor is low-turnover.
- `harness/normalize-*.tsv` is the input to `wiki-family-build.js` (family §3 tables +
  `memberCount`/`bestVariant`). It is **gitignored and has regressed before** — it once fell
  from ~119 normalized rows to 18, which blocked every family page from regenerating.
  The durable copy is the `normalized: { … }` block `kb-stub.js` stamps into each
  `wiki/strategies/*.md`; `node utils/normalize-ledger-rebuild.js` reconstructs the ledger
  from those pages with no backtest cost. Reconstructed rows leave `total_pct` empty (the
  wiki does not store it) — that is how you tell them from measured rows.
- Re-running the same strategy through normalize can shift `annual_pct` by ~0.15pp
  (e.g. −25.87 vs −26.02 for the same file). Measured rows win over reconstructed ones.
- **Screening ranks on MARGINAL information, not pass-likelihood.** Measured on this corpus:
  the 4 most-cloned posts all fail the gate; 57% of gate-passes are 小市值 variants of a family
  that already holds 35; the top-objective strategy (3.595) is an ETF-discount book that dies
  under mild friction. Popularity selects for redundancy. See `screen/screen.md` §1.
- A screener's **hard reject must be a known fact, never a guess**. An early rule dropping
  "titles with no mechanism keyword" discarded 287 of 549 strategies including a held family
  with 4 gate-passes. Vague-looking posts cost ~460 tokens to screen; wrong drops are permanent.
- **问答 (cate=10) is mostly help-desk traffic**: first 200-post screen dropped 94% of Q&A posts vs
  24–30% of 文章/精华. Help-desk posts attach backtests to ask about them, so no payload rule
  catches them. Stored rows now carry `cate`; screen with `--cates 14,3` first. Q&A is
  deferred, not rejected — it still yielded the O'Neil pocket-pivot idea.
- Full 精华+文章 screen (793 posts): fetch-now 50 / fetch 256 / hold 183 / drop 304. The
  fetch-now band spans **25 families, largest 12%** — axis M is doing its job. Screeners
  proposed **71 NEW mechanism families** in the fetch band (all-weather / risk parity, macro
  timing, northbound flow, accrual factors, overnight-gap, commodity cross-section, bonds);
  these are candidate `wiki/families/` pages, not yet registered.
- ⚠ **The fetch band mixes "read this" with "backtest this".** Many top picks score S=0: they
  are write-ups, futures-only, or need data outside 2022–23. Bands rank information, not
  runnability — check `flags` before spending backtest minutes. Candidate fix for a future
  rubric epoch.
- **Never re-request a post body.** `utils/post-cache.js` (`data/post-bodies.json`) caches the
  whole `detailV2` payload keyed by `uniqueKey`, shared by `screen-prefilter.js` and
  `resource-fetch.js`. Post text is immutable, so entries never expire by default. Before it
  existed, re-running the prefilter re-fetched every unscreened candidate and a post that was
  both screened and ingested was fetched twice — thousands of avoidable requests at ~2,600 posts.
- **Screening and normalization are connected through `data/pending-normalize.json`.**
  `utils/normalize-backfill.js` writes the held-but-never-measured strategies into it in
  screening-priority order; `normalize-daily.js` drains it and appends each day's new fetches.
  `strategy-normalize.js --files` preserves the CALLER'S order (it used to re-sort by directory
  listing, which silently discarded the priority). Screening already-fetched posts needs
  `screen-prefilter.js --keys <file>`, because R3 (already fetched) is the right rule for
  "should we download this" and the wrong one for "which file we hold deserves backtest minutes".
- The backfill EXCLUDES S=0 files (harness cannot produce a valid result) and DEFERS files a
  screener flagged as multi-hour — the normalizer's slow-skip cap cancels at 20 min, so one
  such file burns a third of the daily budget to learn nothing.
- **`data/consumption.tsv` records what each stage has consumed** (append-only, tracked). Before
  it, nothing knew which strategies or families had been studied or enhanced — every family page
  read `study: 0, enhance: 0` including families studied to exhaustion. `consumption-report.js`
  turns it into the loops' input queues. Enhance events are keyed by FAMILY, not session tag.
- **Bookkeeping belongs to the step that owns it, not to one caller.** Wiki-stub creation and
  pending-queue pruning lived only in `normalize-daily.js`, so a direct normalizer run silently
  skipped both (3 measured strategies had a ledger row and no page; the queue was stale by 11).
  `utils/normalize-sync.js` derives both from the ledger and runs at the end of every batch.
- **Type-level merging needs the guard in `utils/type-integrate-check.js`.** Blending raises
  Sharpe mechanically whenever correlation < 1 and the gate IS a Sharpe threshold — 七星高照's
  blend scores sharpe 3.17 against legs of 2.85/1.60 and still loses to its own small-cap leg
  (0.4814 vs 0.5984). Beat the best MEMBER, not the gate.
- Screening verdicts live in `screen/verdicts.json` and are applied INSIDE the queue builders,
  because every discovery run rebuilds the queues from scratch.
- Blind-test result (104 posts, 22.1% base rate): judgement on post BODIES scored 0.90 AUC vs
  0.75 for a bare 小市值 keyword and 0.66 for popularity. Title-only screening scores ~0.75 —
  fetch the bodies, they are free via `community/post/detailV2`.
- **Two community lookahead claims were tested and NOT reproduced** (`study/_probes/`,
  2026-09-18): `get_extras('is_st', start_date=D, end_date=D)` agrees exactly with
  `get_current_data()[s].is_st` on two separate TRAIN windows, and an undated
  `get_fundamentals(q)` is identical to `date=context.previous_date`. So the 15 held
  strategies using the `get_extras` ST form and the 130 undated fundamentals calls are clean.
  The 七星高照 NAV-premium lookahead claim is moot: study q-4 measured that filter as exactly
  inert. Still open: LOF/QDII NAV publication lag for the discount families.
- The backtest **log is not retrievable** via the API (`/algorithm/backtest/log` returns empty).
  A probe must encode its answer as a marker trade, and **always needs a control** — `no-trades`
  otherwise cannot be told apart from "the code path never ran". See `study/_probes/README.md`.
- **Harness constants live in `harness/config/epoch-<n>.json`; `active.json` says which is in
  force; code reads them through `utils/harness-config.js`.** They used to be duplicated across
  seven files and had already drifted. Bump an epoch by writing a new JSON + updating
  `active.json`; old epoch files are kept so results stay attached to the rules that made them.
- **Epoch 3 (2026-09-19)**: TRAIN 2022-01-01..2023-12-31 (unchanged), VAL **2024-01-01..2025-12-31**
  (was 2024 only), OOS reserve starts **2026-01-01**. TRAIN and costs are unchanged, so the 122
  epoch-2 TRAIN rows stay directly comparable; only the 2 VAL results are affected and are
  annotated `harness_epoch: 2` in their file headers. The reserve is now ~9 months, so the OOS
  budget tightened to **2 tests per epoch**.
- `enhance/strategy_template.py` and the normalizer's injected OVERRIDE run on JoinQuant's
  servers and **cannot read the JSON** — they hold literal Python. `harness-config.js --verify`
  is what keeps them honest; run it after any cost change.
- Pipeline 2's backtest window is parameterized via `--window train|val` (or `--start/--end`),
  set through the `newStrategy` URL params. The **2026+ OOS window is hard-blocked** (`OOS-BLOCKED`)
  unless `JQ_ALLOW_OOS=1` — see `harness/harness.md`. No flag = JQ default range (ad-hoc).
- Do not close the CDP Chrome process — it invalidates the JQ session and forces re-login.
