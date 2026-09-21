#!/usr/bin/env bash
#
# agent-loop.sh <stage> — RESUME the pinned agent session for one STAGE, unattended.
#
# Parameterized replacement for autoenhance-loop.sh / autostudy-loop.sh, which were ~90%
# identical. That duplication was not cosmetic: the lock-trap bug had to be fixed in both, and
# within one day of fixing the enhance resume nudge the study copy still named a superseded epoch
# in the OOS rule. Two copies of one instruction drift, and the drift is silent.
#
# Stage is the ONLY thing that varies: it selects the session pin (data/auto<stage>-session.txt),
# the log dir, the lock, and the nudge's skill. Everything else — branch gate, session-holder
# check, CDP probe, budget gate, shared pipeline lock, cleanup — is one copy.
#
# The old two scripts are LEFT IN PLACE: launchd jobs and pinned sessions still reference them,
# and this repo does not retire a working path before its replacement has run.
#
# Usage: agent-loop.sh research|enhance|study
# Env:   REPO, USAGE_LIMIT, JQ_CDP_URL, USE_BYPASS, TAG, JQ_PIPELINE_LOCK_HELD
#
set -uo pipefail

STAGE="${1:-}"
case "$STAGE" in
  research|enhance|study) ;;
  *) echo "usage: agent-loop.sh research|enhance|study" >&2; exit 2 ;;
esac

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="${REPO:-$(cd "$SCRIPT_DIR/.." && pwd)}"
USAGE_LIMIT="${USAGE_LIMIT:-55}"
JQ_CDP_URL="${JQ_CDP_URL:-http://localhost:9225}"
LOG_DIR="$REPO/data/auto${STAGE}-logs"
LOCK="$REPO/data/auto${STAGE}.lock"
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
  BRANCH="$STAGE/$TAG"
  if [ "$CUR_BRANCH" != "$BRANCH" ]; then
    log "skip: TAG=$TAG wants '$BRANCH' but HEAD is '$CUR_BRANCH' — check it out yourself; this job does not move your tree"
    exit 0
  fi
else
  BRANCH="$CUR_BRANCH"
fi

# ── Precheck 0: a pinned interactive session exists for THIS branch ──────────
# We RESUME the user's interactive session (same context, no cold start), rather than
# start a fresh one. The session id is pinned by scripts/auto${STAGE}-interactive.sh into
# data/auto${STAGE}-session.txt as "<branch>\t<uuid>". No matching session → nothing to
# resume; skip. (This is what makes the timer safe to leave loaded: it only ever continues
# a session the user has actually started interactively on this branch.)
SID_FILE="$REPO/data/auto${STAGE}-session.txt"
if [ ! -f "$SID_FILE" ]; then
  log "skip: no data/auto${STAGE}-session.txt — start the epoch interactively first (scripts/auto${STAGE}-interactive.sh)"; exit 0
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
# ⚠ The nudge must send the agent to the QUEUE, not to its own memory of the round.
# "continue exactly where you left off" was the whole message, so a resumed session carried on
# with the family it had been working — even after a human had confirmed the next one and
# enhance/ideas-queue.json had been rewritten for it. The queue is where the round's state
# actually lives, and its head may be a blocked/informational entry that changes what to do
# (e.g. "the baseline slow-skipped; retry at a higher cap before dispatching any idea").
#
# ⚠ The OOS boundary is DERIVED, never named. This string used to say "epoch 5: 2026-01-01+";
# the epoch has moved since and the boundary moves with it, so a literal here is a
# hard-to-notice lie sitting next to the one rule the agents must never get wrong.
# The nudge is the ONLY instruction a headless resumed session gets. Shared invariants are
# written once here; each stage contributes only its skill and its unit of work.
case "$STAGE" in
  research) SKILL_LINE="you are running /run-family per .claude/skills/run-family/SKILL.md. FIRST re-read 'node utils/family-queue.js' and take the highest-scoring family whose reason is not done; work exactly ONE family and STOP when it is done — the next fire picks the next one. If its reason is new-members, do the Step 0 early exit first: if the new variants raise no unexplored idea, log their normalized results as section-2 raw rows, record the research consumption event, and exit without opening the loop." ;;
  enhance)  SKILL_LINE="you are already running /run-enhance per enhance/program.md" ;;
  study)    SKILL_LINE="you are already running /run-study per study/program.md, FAMILY-LEVEL; work study/manifest.json in order" ;;
esac

NUDGE="Quota is available again — continue where the ON-DISK state says you are ($SKILL_LINE). FIRST re-read the queue on disk and trust it over your own memory of the last round: it may have been re-pointed at a different family, or its head may be a blocked/informational entry that changes what to do before any idea is dispatched. Backtest cap: have the executor pass --usage-limit $USAGE_LIMIT to the backtester (plain command: no JQ_USAGE_LIMIT= prefix, no | tail) and run it IN THE FOREGROUND (blocking) — never run_in_background and await a notification, it will not re-invoke this headless session. Run ONE backtest at a time: the completion signal is the account-wide running count, concurrent runs have returned identical metrics for different strategies, the backtester refuses with CONCURRENT-STOP and you must not set JQ_ALLOW_CONCURRENT. VAL is budgeted at one validation per (family, epoch) and --window val requires --family; if it is spent, keep iterating on TRAIN and never set JQ_ALLOW_REVAL. NEVER touch the reserved OOS window — run 'node utils/harness-config.js' and read the boundary from it rather than assuming one. Keep going until the JQ budget (used>=$USAGE_LIMIT) or the Anthropic quota is hit, then STOP at a clean git state with a one-line status saying what is still queued. Do NOT git commit wiki/ledgers unless asked."

log "resuming claude ${STAGE} session $SID ($PERM_FLAG) → $RUN_LOG"
JQ_USAGE_LIMIT="$USAGE_LIMIT" claude -p --resume "$SID" "$NUDGE" $PERM_FLAG >"$RUN_LOG" 2>&1
rc=$?
tail -n 3 "$RUN_LOG" 2>/dev/null | sed 's/^/    /' | tee -a "$LOG_DIR/wrapper.log" >/dev/null
if [ $rc -ne 0 ]; then
  log "claude exited rc=$rc (likely rate-limited — next fire retries after quota reset)"
else
  log "resume complete rc=0"
fi
exit 0
