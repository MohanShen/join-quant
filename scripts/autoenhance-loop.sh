#!/bin/bash
#
# autoenhance-loop.sh — RESUME the user's autoenhance session unattended.
#
# Fired on a schedule by launchd (see scripts/com.mohanshen.join-quant-autoenhance.plist).
# Solves the "Anthropic per-time-slot usage limit" problem for the AUTORESEARCH pipeline:
# each firing is a cheap poll that RESUMES the SAME claude session the user started
# interactively (scripts/autoenhance-interactive.sh pins its session id). Because it
# resumes (`claude -p --resume <uuid>`) rather than cold-starting, the agents keep full
# context — no re-reading/re-initializing. When the Anthropic quota is available it does
# real work; when it's exhausted the resume exits fast, so the next firing after the reset
# picks the same session back up automatically.
#
# Preconditions the wrapper checks (exits 0 = clean no-op if any fails):
#   0. A pinned session exists for this branch (data/autoenhance-session.txt) AND it's not
#      currently active (transcript mtime older than HEARTBEAT_MIN — a quota-blocked session
#      is idle even if its window is open, so it becomes resumable).
#   1. CDP Chrome reachable at $JQ_CDP_URL — backtests need the logged-in session.
#   2. JQ daily backtest budget not exhausted — used < USAGE_LIMIT.
#   Plus a PID lockfile so two fires never overlap.
#
# Env overrides:
#   REPO         repo root (default: parent of this script's dir)
#   TAG          optional: require branch enhance/$TAG. Default: whatever branch is checked
#                out (parity with autostudy-loop.sh). This job never moves your tree.
#   USAGE_LIMIT  JQ backtest-minute cap (default 55 = free tier only; >60 spends credits)
#   HEARTBEAT_MIN session-active threshold in minutes (default 20)
#   JQ_CDP_URL   CDP endpoint (default http://localhost:9225)
#   USE_BYPASS   if =1, run claude with --dangerously-skip-permissions instead of the
#                project .claude/settings.json allowlist (use only if a run stalls)
#
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
LOG_DIR="$REPO/data/autoenhance-logs"
LOCK="$REPO/data/autoenhance.lock"
PLOCK="$REPO/data/jq-pipeline.lock"   # shared across enhance+study crons: only one JQ pipeline runs at a time
mkdir -p "$LOG_DIR"

ts() { date '+%Y-%m-%d %H:%M:%S'; }
log() { echo "[$(ts)] $*" | tee -a "$LOG_DIR/wrapper.log"; }

cd "$REPO" || { log "FATAL: cannot cd to $REPO"; exit 1; }

# ── Lock: don't overlap a still-running fire ────────────────────────────────
if [ -e "$LOCK" ]; then
  lockpid="$(cat "$LOCK" 2>/dev/null)"
  if [ -n "$lockpid" ] && kill -0 "$lockpid" 2>/dev/null; then
    log "skip: previous run (pid $lockpid) still active"; exit 0
  fi
  log "stale lock (pid ${lockpid:-?}) — clearing"
fi
echo $$ > "$LOCK"
# ⚠ Only remove the SHARED lock if we actually acquired it. This trap used to run
# unconditionally, and it is installed long before the PLOCK acquisition below — so a fire
# that correctly skipped ("another JQ pipeline is running") still deleted the *holder's*
# lock on its way out, silently breaking mutual exclusion for whoever was mid-backtest.
PLOCK_MINE=0
cleanup() { rm -f "$LOCK"; [ "$PLOCK_MINE" = "1" ] && rm -f "$PLOCK"; }
trap cleanup EXIT

# ── Resolve enhance branch ─────────────────────────────────────────────────
# Any branch is allowed, exactly as scripts/autostudy-loop.sh already does. The gate that
# matters is Precheck 0 below: we only resume a session pinned to the branch currently
# checked out, so a stray fire on an unrelated branch still no-ops.
#
# ⚠ This used to hard-require an `enhance/*` branch and `git checkout` its way there. Both
# were fossils of the pre-rename era (docs/pipeline-refactor-plan.md renamed research/ ->
# enhance/), and both were actively harmful once the rest of the pipeline moved to main:
#   - no `enhance/*` branch exists any more, so every fire logged "skip" and exit 0 — a cron
#     that reports success daily while starting nothing;
#   - the checkout silently switched the WORKING TREE out from under whatever else was
#     running, which for a timer-driven job sharing a repo is not an acceptable side effect.
# TAG still forces a specific branch when you genuinely want epoch branches back.
CUR_BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"
if [ -z "$CUR_BRANCH" ]; then
  log "skip: cannot resolve current branch (not a git repo / detached HEAD)"; exit 0
fi
TAG="${TAG:-}"
if [ -n "$TAG" ]; then
  BRANCH="enhance/$TAG"
  if [ "$CUR_BRANCH" != "$BRANCH" ]; then
    log "skip: TAG=$TAG wants '$BRANCH' but HEAD is '$CUR_BRANCH' — check it out yourself; this job does not move your tree"
    exit 0
  fi
else
  BRANCH="$CUR_BRANCH"
fi

# ── Precheck 0: a pinned interactive session exists for THIS branch ──────────
# We RESUME the user's interactive session (same context, no cold start), rather than
# start a fresh one. The session id is pinned by scripts/autoenhance-interactive.sh into
# data/autoenhance-session.txt as "<branch>\t<uuid>". No matching session → nothing to
# resume; skip. (This is what makes the timer safe to leave loaded: it only ever continues
# a session the user has actually started interactively on this branch.)
SID_FILE="$REPO/data/autoenhance-session.txt"
if [ ! -f "$SID_FILE" ]; then
  log "skip: no data/autoenhance-session.txt — start the epoch interactively first (scripts/autoenhance-interactive.sh)"; exit 0
fi
SID_BRANCH="$(cut -f1 "$SID_FILE" 2>/dev/null)"
SID="$(cut -f2 "$SID_FILE" 2>/dev/null)"
if [ "$SID_BRANCH" != "$BRANCH" ] || [ -z "$SID" ]; then
  log "skip: session file is for '$SID_BRANCH' (uuid ${SID:-none}), not current branch '$BRANCH'"; exit 0
fi
# Locate the session transcript (unique by uuid across project dirs).
TRANSCRIPT="$(ls -t "$HOME"/.claude/projects/*/"$SID".jsonl 2>/dev/null | head -1)"
if [ -z "$TRANSCRIPT" ]; then
  log "skip: no transcript yet for session $SID — start it interactively first"; exit 0
fi

# ── Precheck 0b: is another live process HOLDING this session? ──────────────
# A `claude` process whose args carry this session id = the interactive TUI (or a run) is
# holding the session. We cannot resume a session another process holds, so skip. This is
# the accurate signal (the old transcript-mtime heuristic deadlocked: a left-open idle TUI
# keeps the transcript warm, so the cron skipped forever). If NO process holds it, the
# session is free to resume regardless of transcript age. PID lockfile above covers
# fire-vs-fire; this covers fire-vs-interactive.
#
# NOTE: to hand a running interactive session off to the cron you must CLOSE it (exit the
# TUI). Leaving it open — even idle after a quota stop — keeps holding the session and the
# cron will (correctly) stand aside, logging the message below.
HOLDER="$(pgrep -f "$SID" 2>/dev/null | tr '\n' ' ')"
if [ -n "$HOLDER" ]; then
  log "skip: session $SID is held by live claude pid(s) ${HOLDER}. If that's an interactive TUI you left open, CLOSE it to let the cron resume."; exit 0
fi

# ── Precheck 1: CDP Chrome alive ────────────────────────────────────────────
# In remote mode the browser lives on the QMT server behind an SSH tunnel, which a
# launchd-spawned shell won't have inherited. Try to bring it up before giving up,
# otherwise an unattended fire skips forever with the server sitting there idle.
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  bash "$(dirname "$0")/cdp-tunnel.sh" up >/dev/null 2>&1 || true
fi
if ! curl -s -m 5 "$JQ_CDP_URL/json/version" >/dev/null 2>&1; then
  log "skip: CDP Chrome not reachable at $JQ_CDP_URL — keep it running to allow backtests"; exit 0
fi

# ── Precheck 2: JQ daily budget not exhausted ───────────────────────────────
# Read the real budget via the CDP-authenticated helper (plain curl can't — JQ cookies
# are httpOnly in Chrome). If it can't get a reading, proceed and let the pipeline's own
# usage-gate (USAGE-STOP) enforce the limit authoritatively.
BUDGET="$(node utils/jq-budget.js 2>/dev/null)"
USED="$(printf '%s' "$BUDGET" | sed -n 's/.*used=\([0-9]*\).*/\1/p')"
if [ -n "$USED" ] && [ "$USED" -ge "$USAGE_LIMIT" ] 2>/dev/null; then
  log "skip: JQ budget used=${USED}min >= limit=${USAGE_LIMIT}min — wait for daily reset"; exit 0
fi
# ── Shared lock: don't run backtests while the OTHER pipeline (study/enhance) runs ──
if [ "${JQ_PIPELINE_LOCK_HELD:-0}" = "1" ]; then
  # Invoked by scripts/daily-pipeline.sh, which already holds the shared lock. Without this
  # the parent's own lock made every nested dispatch skip and exit 0 — the planner then
  # recorded "ran" for work that never started.
  log "shared lock held by caller (JQ_PIPELINE_LOCK_HELD=1) — proceeding without re-taking it"
elif [ -e "$PLOCK" ]; then
  pp="$(cat "$PLOCK" 2>/dev/null)"
  if [ -n "$pp" ] && kill -0 "$pp" 2>/dev/null; then log "skip: another JQ pipeline (pid $pp) is running — serialize"; exit 0; fi
fi
echo $$ > "$PLOCK"
PLOCK_MINE=1
log "budget ok (used=${USED:-unknown}min); resuming session $SID on $BRANCH"

# ── Resume the interactive session headless ─────────────────────────────────
# claude -p --resume <uuid> continues the SAME conversation with full context — the agents
# do not re-read/re-initialize from scratch. A short nudge is enough; the plan already
# lives in the session.
PERM_FLAG="--permission-mode acceptEdits"
[ "${USE_BYPASS:-0}" = "1" ] && PERM_FLAG="--dangerously-skip-permissions"

RUN_LOG="$LOG_DIR/run-$(date '+%Y%m%d-%H%M%S').log"
NUDGE="Quota is available again — continue the autoenhance loop exactly where you left off (you are already running /run-enhance per enhance/program.md). Backtest cap: have the engineer pass --usage-limit $USAGE_LIMIT to the backtester (plain command: no JQ_USAGE_LIMIT= prefix, no | tail). NEVER touch the reserved OOS window (epoch 5: 2026-01-01+; confirm with `node utils/harness-config.js` — the boundary moves with the epoch, and 2025 is now VAL). Keep iterating until the JQ budget (used>=$USAGE_LIMIT) or the Anthropic quota is hit again, then STOP at a clean git state with a one-line status. Do NOT git commit wiki/results unless asked."

log "resuming claude session $SID ($PERM_FLAG) → $RUN_LOG"
JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --resume "$SID" "$NUDGE" $PERM_FLAG >"$RUN_LOG" 2>&1
rc=$?
tail -n 3 "$RUN_LOG" 2>/dev/null | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
if [ $rc -ne 0 ]; then
  log "claude exited rc=$rc (likely rate-limited — next fire retries after quota reset)"
else
  log "resume complete rc=0"
fi
exit 0
