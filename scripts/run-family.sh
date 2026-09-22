#!/usr/bin/env bash
#
# run-family.sh [family] — run the merged research loop on ONE family.
#
# ## Why this is not agent-loop.sh
#
# `agent-loop.sh <stage>` resumes ONE session pinned per STAGE. That model is wrong for a loop
# whose unit of work is a family, and it misfired in exactly the predictable way: the single
# pinned enhance session carried ETF动量's whole context forward, so when the queue was re-pointed
# at ETF溢价 the resumed session kept working ETF动量 — it was told to "continue exactly where you
# left off", and it did. Its idea-1 also flagged ITSELF as 新颖度为零, re-proposing a configuration
# the family already held, which is what a long contaminated context produces.
#
# So: **one family, one session, clean history.** A new family gets a brand-new session id and no
# inherited transcript. The family page, `study/<family>/queue.json` and `findings.tsv` are the
# handoff — they are on disk precisely so that context does not have to be.
#
# Resume is still right WITHIN a family: a round stopped by the daily budget picks up its own
# session, because that context is about the family it is still working.
#
#   pins: data/research-sessions/<family>.txt   ("<branch>\t<uuid>")
#
# Usage:
#   scripts/run-family.sh                 # take the top family from the queue
#   scripts/run-family.sh 大小盘轮动        # a named family
#   scripts/run-family.sh --list          # show the queue and each family's session state
#   FRESH=1 scripts/run-family.sh <fam>   # force a new session even if one is pinned
#   DRY=1   scripts/run-family.sh <fam>   # print what would run
#
# Env: REPO, USAGE_LIMIT (default 55), JQ_CDP_URL, USE_BYPASS
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
PIN_DIR="$REPO/data/research-sessions"
LOG_DIR="$REPO/data/autoresearch-logs"
LOCK="$REPO/data/autoresearch.lock"
PLOCK="$REPO/data/jq-pipeline.lock"
mkdir -p "$PIN_DIR" "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }
cd "$REPO" || { echo "FATAL: cannot cd to $REPO" >&2; exit 1; }

# ── --list ──────────────────────────────────────────────────────────────────
if [ "${1:-}" = "--list" ]; then
  node utils/family-queue.js
  echo
  echo "  session state:"
  shopt -s nullglob
  for f in "$PIN_DIR"/*.txt; do
    fam="$(basename "$f" .txt)"
    sid="$(cut -f2 "$f" 2>/dev/null)"
    alive="$(ls "$HOME"/.claude/projects/*/"$sid".jsonl 2>/dev/null | head -1)"
    printf '   %-14s %s  %s\n' "$fam" "${sid:0:8}" "${alive:+transcript present}"
  done
  shopt -u nullglob
  exit 0
fi

FAMILY="${1:-}"
if [ -z "$FAMILY" ]; then
  FAMILY="$(node -e '
    const q = require("./utils/family-queue").build();
    // Prefer the human-ordered list when one exists; else fall back to score order.
    let ordered = [];
    try { ordered = require("./data/family-queue.json").queue.map(r => r.family); } catch {}
    const due = new Set(q.due.map(f => f.family));
    const pick = ordered.find(f => due.has(f)) || (q.due[0] || {}).family || "";
    process.stdout.write(pick);
  ' 2>/dev/null)"
  [ -z "$FAMILY" ] && { log "nothing due — family queue is empty"; exit 0; }
  log "no family given; took the queue head: $FAMILY"
fi

[ -f "$REPO/wiki/families/$FAMILY.md" ] || { log "FATAL: no such family page: wiki/families/$FAMILY.md"; exit 1; }

# ── one fire at a time ──────────────────────────────────────────────────────
if [ -e "$LOCK" ]; then
  lp="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lp" ] && kill -0 "$lp" 2>/dev/null; then log "skip: a research fire (pid $lp) is already running"; exit 0; fi
  log "stale lock (pid ${lp:-?}) — clearing"
fi
echo $$ > "$LOCK"
PLOCK_MINE=0
cleanup() { rm -f "$LOCK"; [ "$PLOCK_MINE" = "1" ] && rm -f "$PLOCK"; }
trap cleanup EXIT

# ── preflight: CDP, then budget ─────────────────────────────────────────────
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  bash "$SCRIPT_DIR/cdp-tunnel.sh" up >/dev/null 2>&1 || true
fi
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  log "skip: CDP Chrome not reachable at $JQ_CDP_URL"; exit 0
fi
BUDGET="$(node utils/jq-budget.js 2>/dev/null)"
USED="$(printf '%s' "$BUDGET" | sed -n 's/.*used=\([0-9]*\).*/\1/p')"
if [ -n "$USED" ] && [ "$USED" -ge "$USAGE_LIMIT" ] 2>/dev/null; then
  log "skip: JQ budget used=${USED}min >= limit=${USAGE_LIMIT}min — wait for the daily reset"; exit 0
fi

if [ "${JQ_PIPELINE_LOCK_HELD:-0}" = "1" ]; then
  log "shared lock held by caller — proceeding without re-taking it"
elif [ -e "$PLOCK" ]; then
  pp="$(cat "$PLOCK" 2>/dev/null)"
  if [ -n "$pp" ] && kill -0 "$pp" 2>/dev/null; then log "skip: another JQ pipeline (pid $pp) is running"; exit 0; fi
  echo $$ > "$PLOCK"; PLOCK_MINE=1
else
  echo $$ > "$PLOCK"; PLOCK_MINE=1
fi

# ⚠ Say whether an EMPTY family is empty on purpose.
#
# A fresh session has no context by design, so it cannot tell a deliberate reset from an accident.
# The first from-scratch run proved it: the session found a scaffolded page, a missing study/
# directory and removed consumption rows, concluded the tree had been wiped by mistake, and
# correctly refused to run — it would otherwise have re-bought findings that HEAD already held.
# Refusing was the right call on the evidence it had; the missing piece was the intent, which only
# the caller knows. So the caller states it.
FROM_SCRATCH=0
if [ ! -d "$REPO/study/$FAMILY" ] \
   && ! grep -q "^$FAMILY	" "$REPO/data/consumption.tsv" 2>/dev/null; then
  FROM_SCRATCH=1
fi

# ── resume this FAMILY's own session, or start a clean one ──────────────────
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
PIN="$PIN_DIR/$FAMILY.txt"
SID=""
MODE="new"

# ⚠ A from-scratch family NEVER resumes. Any pinned session predates the reset, so resuming it
# hands back the very context the reset was meant to clear — including, in the first attempt, a
# session whose whole conclusion was "the tree has been wiped, I refuse to run".
if [ "$FROM_SCRATCH" = "1" ] && [ -f "$PIN" ]; then
  log "from-scratch family: discarding the pre-reset pin ${PIN##*/}"
  rm -f "$PIN"
fi

if [ "${FRESH:-0}" != "1" ] && [ "$FROM_SCRATCH" != "1" ] && [ -f "$PIN" ]; then
  pin_branch="$(cut -f1 "$PIN" 2>/dev/null)"
  pin_sid="$(cut -f2 "$PIN" 2>/dev/null)"
  if [ "$pin_branch" = "$BRANCH" ] && [ -n "$pin_sid" ] \
     && ls "$HOME"/.claude/projects/*/"$pin_sid".jsonl >/dev/null 2>&1; then
    # Only resume if nothing else holds it — a live TUI owns the session.
    holder="$(pgrep -f "$pin_sid" 2>/dev/null | tr '\n' ' ')"
    if [ -n "$holder" ]; then
      log "skip: $FAMILY's session $pin_sid is held by pid(s) $holder — close it to hand off"; exit 0
    fi
    SID="$pin_sid"; MODE="resume"
  fi
fi

if [ -z "$SID" ]; then
  SID="$(uuidgen | tr 'A-Z' 'a-z')"
  printf '%s\t%s\n' "$BRANCH" "$SID" > "$PIN"
fi

RUN_LOG="$LOG_DIR/$FAMILY-$(date '+%Y%m%d-%H%M%S').log"
PERM_FLAG="--permission-mode acceptEdits"
[ "${USE_BYPASS:-0}" = "1" ] && PERM_FLAG="--dangerously-skip-permissions"

SCRATCH_NOTE=""
if [ "$FROM_SCRATCH" = "1" ]; then
  SCRATCH_NOTE="
INTENT: this family is empty ON PURPOSE. There is no study/$FAMILY directory, no findings, no
queue and no consumption history, and the family page is a freshly generated scaffold. That is the
starting state you are meant to build from, NOT damage — do not treat it as a wipe to be restored,
and do not go looking in git history for prior findings to reuse. §3 is auto-generated and is your
only measured input. Build the page: draft the edge: block, raise the first understand questions,
and fill §1 from the base source."
fi

# A NEW session gets the full brief — it has no history to continue. A RESUMED one is mid-round on
# THIS family, so it is pointed back at the on-disk state rather than re-briefed.
if [ "$MODE" = "new" ]; then
  PROMPT="/run-family $FAMILY

This is a FRESH session for this family: you have no prior context, and the on-disk state is the
whole handoff — wiki/families/$FAMILY.md, study/$FAMILY/queue.json, study/$FAMILY/findings.tsv.
Start by running 'node utils/research-queue.js $FAMILY' and reading the family page, exactly as the
skill requires. Work ONLY this family and stop when it is done. Backtest cap: pass
--usage-limit $USAGE_LIMIT, foreground/blocking, ONE backtest at a time. Stop at a clean git state
with a one-line status naming what is still queued.$SCRATCH_NOTE"
else
  PROMPT="/run-family $FAMILY

Continuing this family's own session after a budget stop. Re-read
'node utils/research-queue.js $FAMILY' FIRST and trust the on-disk queue over your memory: ideas may
have been answered, closed, or re-ranked since. Same caps: --usage-limit $USAGE_LIMIT, foreground,
one backtest at a time. Stop at a clean git state with a one-line status."
fi

log "$MODE session ${SID:0:8} for family $FAMILY (branch $BRANCH, budget ${USED:-?}/${USAGE_LIMIT}min) -> $RUN_LOG"

if [ "${DRY:-0}" = "1" ]; then
  log "DRY=1 — would run: claude -p $( [ "$MODE" = resume ] && echo "--resume $SID" || echo "--session-id $SID" ) $PERM_FLAG"
  echo "--- prompt ---"; echo "$PROMPT"
  exit 0
fi

if [ "$MODE" = "resume" ]; then
  JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --resume "$SID" "$PROMPT" $PERM_FLAG >"$RUN_LOG" 2>&1
else
  JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --session-id "$SID" "$PROMPT" $PERM_FLAG >"$RUN_LOG" 2>&1
fi
rc=$?
tail -n 3 "$RUN_LOG" 2>/dev/null | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
if [ $rc -ne 0 ]; then
  log "claude exited rc=$rc (likely rate-limited — the pin is kept, next fire resumes this family)"
else
  log "$FAMILY: run complete rc=0 — check its ledger, exit 0 is not proof work happened"
fi
exit 0
