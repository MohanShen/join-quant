# Pipeline Refactor Plan — family-level study + auto-enhance

Status: in progress. Goal: pivot auto-study and (renamed) auto-enhance to operate on
**strategy families** (`wiki/families/*.md`), and reserve the name "auto-research" for a
future broad pipeline (new data / factors / trading ideas).

## 0. Structural decision: partition `research/`
`research/` mixes shared infra with enhance-specific artifacts. Split them:

| Current | Kind | → Moves to |
|---|---|---|
| `research/harness.md` | shared (study + enhance + future) | `harness/harness.md` |
| `research/normalize-train.tsv`, `normalize-*.tsv` | shared (normalize output) | `harness/` |
| `research/strategy_template.py` | enhance | `enhance/` |
| `research/program.md` | enhance | `enhance/program.md` |
| `research/candidates/`, `results.tsv`, `ideas-queue.json`, `loop-state.json` | enhance | `enhance/` |

`research/` ends empty, reserved for the future auto-research pipeline.

## 1. Harness + infra relocation (Commit 1)
- `git mv research/harness.md harness/harness.md`; move normalize ledgers to `harness/`.
- Global replace `research/harness.md` → `harness/harness.md` across `.md/.sh/.js` (excl. node_modules):
  8 agents, 2 skills, `study/program.md`, `research/program.md`, `docs/*-schema.md`, README, CLAUDE.md, 3 JS utils, 82 archived `wiki/studies/` frontmatter refs.
- JS path updates: `strategy-normalize.js` (writes `normalize-<window>.tsv`), `wiki-family-build.js` + `normalize-daily.js` (read it); `.gitignore` `research/normalize-*` → `harness/normalize-*`. Verify with a `--dry-run`.

## 2. Auto-study → family-level (Commit 2) — keeps its name
- `study/manifest.json`: list of **families** (status per family), not strategies.
- `study/program.md`: target = family; read `wiki/families/<fam>.md`; questions family-scoped —
  (a) why base works, (b) **why each variant's change moved the result** (recursion).
- Agents (shape unchanged, prompts rewritten): questioner family-level Qs; prioritizer dedup vs family study-log;
  experimenter runs variant/probe + compares across family variants; **analyst writes back to the family page** —
  variant Δ → §2, question→conclusion → new **§6 研究问答 (study-log)**.
- `docs/study-schema.md` + `wiki-schema.md §3.3`: §6 (study-owned, append-only); §2 written by normalize + study + enhance (source-tagged).
- Working dirs `study/<id>/` → `study/<family>/`; `.gitignore` update.
- Existing 82 `wiki/studies/` = archive (untouched except harness sed).

## 3. Auto-research → auto-enhance
### 3a — pure rename, behavior parity (Commit 3)
| From | To |
|---|---|
| `research/program.md` | `enhance/program.md` |
| `.claude/agents/autoresearch-{ideator,critic,engineer,recorder}.md` | `autoenhance-{…}.md` |
| `.claude/skills/run-experiment/` | `.claude/skills/run-enhance/` |
| `scripts/autoresearch-interactive.sh` / `-loop.sh` | `autoenhance-…` |
| `scripts/…-autoresearch.plist` | `…-autoenhance.plist` (Label + ProgramArguments) |
| `data/autoresearch-session.txt` | `data/autoenhance-session.txt`; branch `research/<tag>`→`enhance/<tag>` |
| `docs/research-schema.md` | `docs/enhance-schema.md` |

- launchctl: unload old `autoresearch` agent (loaded, firing against dead epoch), load renamed `autoenhance`.
- README + CLAUDE: rename pipeline, reserve "auto-research" for the future broad pipeline.

### 3b — family-level enhance behavior (Commit 4)
- ideator: (1) within-family (from §4 待研究 + §2/§3); (2) **cross-family borrow** (scan other families' §1/§2);
  (3) **new-family by combination** (combine ≥2 families).
- critic: validate vs controlled family vocab; ground the borrow; new family not a dup.
- engineer: candidate under `enhance/candidates/`, harness backtest, TRAIN-iterate / VAL-finalize.
- recorder: result → new §2 variant on the family page (not per-strategy `wiki/experiments/`); on new family, register vocab (§2.2) + scaffold page; archive validated to `validated_strategies/`.
- `docs/enhance-schema.md` + `wiki-schema.md`: new-family registration; enhance-writes-to-family contract.

## 4. Final wiring (Commit 5)
- Cron reload verified; README/CLAUDE pipeline map updated; `wiki-family-build.js` optionally lints §6 + §2 source tags.

## Risks
- Large sed diff through 82 archive pages (low risk — doc refs).
- Loaded cron must be unloaded before plist rename.
- Dead `research/jul12` pin discarded; enhance starts clean on `enhance/<tag>`.
- Normalize-ledger move needs JS path + `.gitignore` tested before relying on it.
