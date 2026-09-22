#!/usr/bin/env bash
#
# run-assign.sh — dispatch the family-assign agent over the unassigned normalized strategies.
#
# The funnel step between `normalize` and the family queue. A normalized strategy with no
# `family:` is INVISIBLE: wiki-family-build.js skips pages without one, so it never joins a family
# page, never reaches the queue, and never gets researched.
#
# Costs NO backtest minutes — it reads source and decides — so it has no budget gate and does not
# take the shared JQ pipeline lock. It does need CDP for nothing at all, so it does not probe it.
#
# One-shot: a fresh session each time, no pin. There is no per-family continuity to preserve here
# and a stale transcript would carry stale family definitions.
#
# Usage: scripts/run-assign.sh [--dry]
#
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LOG_DIR="$REPO/data/autoresearch-logs"
mkdir -p "$LOG_DIR"
cd "$REPO" || exit 1
ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }

PENDING="$(node -e 'process.stdout.write(String(require("./utils/family-assign").pending().length))' 2>/dev/null)"
if [ "${PENDING:-0}" = "0" ]; then
  log "assign: nothing pending — every normalized strategy has a family"
  exit 0
fi

PROMPT="Assign strategy families. $PENDING normalized strategy(ies) have no \`family:\` and are
invisible to the family queue.

Use the family-assign agent's rules (.claude/agents/family-assign.md). Start with
'node utils/family-assign.js' for the pending list and '--evidence <sourceFile>' per candidate,
then READ the strategy source and the candidate family pages' base: before deciding — the matcher
abstains on 82% of pages and is a proposer, not a decider.

Assign with 'node utils/family-assign.js --assign <sourceFile> --family <name> --why \"...\"
--confidence high|med|low'. Leaving a write-up or an analysis post UNASSIGNED is a correct
outcome, not a failure. Do not pass --combination-ack or --new-family to get past a refusal you
have not investigated. Run 'node utils/wiki-family-build.js' at the end if you assigned anything.
Stop at a clean git state with a one-line status."

if [ "${1:-}" = "--dry" ]; then echo "$PROMPT"; exit 0; fi

SID="$(uuidgen | tr 'A-Z' 'a-z')"
RUN_LOG="$LOG_DIR/assign-$(date '+%Y%m%d-%H%M%S').log"
log "assign: $PENDING pending -> new session ${SID:0:8} -> $RUN_LOG"
claude -p --session-id "$SID" "$PROMPT" --permission-mode acceptEdits >"$RUN_LOG" 2>&1
rc=$?
tail -n 3 "$RUN_LOG" | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
log "assign: rc=$rc; $(node -e 'process.stdout.write(String(require("./utils/family-assign").pending().length))' 2>/dev/null) still unassigned"
exit 0
