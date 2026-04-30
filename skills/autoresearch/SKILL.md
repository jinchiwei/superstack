---
name: autoresearch
description: Long-running autonomous research loop. Use when the user wants to iterate over a search space (architectures, input modes, hyperparams, etc.) for hours-to-days, with adaptive replanning, agentic code-fix on failures, optional research-log push, and a STOP-file kill switch. Invocation form: `/autoresearch "<scope text>"`. Self-paces via ScheduleWakeup; user invokes once and walks away.
---

# /autoresearch

Long-running autonomous research loop. One invocation = one session that may span hours or days. Skill body = one iteration; ScheduleWakeup fires the next iteration. State persists at `~/.gstack/projects/<slug>/autoresearch/`.

## Modes

The skill operates in one of two modes based on whether `state.json` exists for this project:

- **INIT mode** — first invocation in a session. Parses scope, enumerates axes, asks user to confirm/edit ONCE, writes state.json, schedules first iteration.
- **RUNNING mode** — subsequent invocations (fired by ScheduleWakeup). Reads state.json, runs one iteration, replans, schedules next.

## Pre-flight

Run this every invocation, regardless of mode. Determines slug, state dir, and which mode applies.

```bash
SKILL_DIR="$HOME/arcadia/superstack/skills/autoresearch"
slug=$("$SKILL_DIR/bin/slug-from-cwd")
home="${GSTACK_HOME:-$HOME/.gstack}"
state_dir="$home/projects/$slug/autoresearch"
state_file="$state_dir/state.json"
mkdir -p "$state_dir"

# STOP file is checked first — if user touched it, finish whatever's appropriate and exit.
if "$SKILL_DIR/bin/stop-check" --slug "$slug"; then
  echo "STOP file present"
  STOP_PRESENT=1
else
  STOP_PRESENT=0
fi

if [[ -f "$state_file" ]]; then
  # state-validate exit codes (D3): 0=valid, 1=corrupt, 2=schema older, 3=schema newer
  "$SKILL_DIR/bin/state-validate" --slug "$slug"
  validate_status=$?
  case "$validate_status" in
    0)
      MODE="running"
      ;;
    1)
      echo "state.json is corrupt — refusing to continue. Inspect $state_file." >&2
      exit 1
      ;;
    2)
      echo "state.json schema is older than current; running state-migrate..."
      if "$SKILL_DIR/bin/state-migrate" --slug "$slug"; then
        MODE="running"
      else
        # Migration failure → defer to user via mailbox; do not run.
        {
          echo ""
          echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ)"
          echo ""
          echo "**Context:** state.json schema migration failed during pre-flight."
          echo ""
          echo "**Question:** Manually inspect $state_file and either upgrade or delete it."
          echo ""
          echo "**Best guess used:** refused to run this iteration"
        } >> "$state_dir/QUESTIONS_FOR_USER.md"
        exit 1
      fi
      ;;
    3)
      echo "state.json is from a newer superstack version. Either upgrade or delete $state_file to start fresh." >&2
      exit 1
      ;;
  esac
  PHASE=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .phase)
  ITER=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .iteration_count)

  # D1 resume reconciliation: if pending_stash_ref is non-null, the previous
  # iteration was interrupted mid-fix. Append a recovery note to the mailbox
  # and clear the field. Do NOT auto-pop — working tree may have drifted.
  pending_ref=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .pending_stash_ref)
  if [[ "$pending_ref" != "null" && -n "$pending_ref" ]]; then
    {
      echo ""
      echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ)"
      echo ""
      echo "**Context:** previous iteration interrupted mid-fix (pending_stash_ref=$pending_ref)."
      echo ""
      echo "**Question:** stash $pending_ref may still be in \`git stash list\`. Inspect and decide whether to pop or drop."
      echo ""
      echo "**Best guess used:** cleared pending_stash_ref and continued"
    } >> "$state_dir/QUESTIONS_FOR_USER.md"
    "$SKILL_DIR/bin/state-update" --slug "$slug" --set '.pending_stash_ref = null'
  fi

  echo "MODE=running phase=$PHASE iter=$ITER slug=$slug"
else
  MODE="init"
  echo "MODE=init slug=$slug"
fi
```

## INIT mode

Triggered when no valid state.json exists.

### Step 1 — Parse scope

The user invocation is `/autoresearch "<scope>"`. The scope arg is in `$ARGS` or whatever the harness passes. If empty, ask the user once via AskUserQuestion to provide one (this is allowed — pre-launch, before the no-questions invariant kicks in).

### Step 2 — Read project context

Use Read on `CLAUDE.md`, `README.md`, and 1-2 obviously relevant source files if present. Just enough to ground the axis enumeration. Don't read the world.

### Step 3 — Enumerate axes via the LLM

Apply the prompt at `prompts/axis-enumeration.md` with:
- `scope`: the scope text
- `project_context`: a brief summary of what you read

Produce the JSON with `scope_slug`, `target_metric`, `axes`, `rationale`.

If the LLM returns `{"error": ...}`, surface the error to the user via AskUserQuestion: "Scope didn't parse — <reason>. Provide a clearer scope or cancel?" Then either re-attempt with the new scope or exit with phase=cancelled.

### Step 4 — Show planned axes + ask user to confirm

This is the **only blocking AskUserQuestion in the entire skill workflow.** Pre-launch, before walking away. After this, the no-questions invariant kicks in.

Use AskUserQuestion with the rendered axes:

```
Plan: <scope_slug>
Target: <target_metric or "no explicit target — stop on exhaustion">
Axes:
  arch: [unet, transformer, mlp]
  input: [t1, t2, dwi]
  loss: [mse, smoothl1]
Cartesian product = N candidates.

Confirm and launch, edit, or cancel?
```

Options:
- **A) Confirm and launch (recommended)** — write state.json with phase=running, schedule first iteration
- **B) Edit axes inline** — let user redirect via "Other" free-text
- **C) Cancel** — exit cleanly, no state.json written

### Step 5 — Initialize state.json

Build the candidate queue from the Cartesian product of axes. Random shuffle within priority groups (later replans will reweight).

```bash
# Pipe an axes JSON to state-init
echo "$AXES_JSON" | "$SKILL_DIR/bin/state-init" --slug "$slug"
"$SKILL_DIR/bin/state-update" --slug "$slug" --set ".candidate_queue = $QUEUE_JSON | .phase = \"running\""
```

### Step 6 — Initialize research-log entry (or fall back)

```bash
if "$SKILL_DIR/bin/research-log-detect"; then
  # Compute top-level project name (brainlab/wolong/curiedx) from project conventions.
  # SKILL.md prose: ask the LLM to infer from CLAUDE.md or fall back to "brainlab" with a note.
  TOP_LEVEL=<inferred>
  PROJECT_SLUG="$slug"
  ENTRY=$(printf "%s\n" "$INITIAL_ENTRY_BODY" | \
    "$SKILL_DIR/bin/research-log-init-entry" \
      --top-level "$TOP_LEVEL" \
      --project "$PROJECT_SLUG" \
      --scope-slug "$SCOPE_SLUG")
  "$SKILL_DIR/bin/state-update" --slug "$slug" \
    --set ".research_log.available = true | .research_log.session_path = \"$ENTRY\""
else
  "$SKILL_DIR/bin/state-update" --slug "$slug" \
    --set ".research_log.available = false | .research_log.fallback_path = \"$home/projects/$slug/autoresearch/notes.md\""
  printf "%s\n" "$INITIAL_ENTRY_BODY" | "$SKILL_DIR/bin/notes-append-local" --slug "$slug"
fi
```

`$INITIAL_ENTRY_BODY` is rendered by the LLM following the existing research-log format rules (h1 title, structured blurb on line 3, Date / Project / Status block, Why, Plan, Axes, Target).

### Step 7 — Schedule first iteration

Use the **ScheduleWakeup** tool:

```
ScheduleWakeup(
  delaySeconds=60,
  prompt="/autoresearch",
  reason="autoresearch INIT confirmed; iteration 1 scheduled"
)
```

After ScheduleWakeup returns, exit (the next invocation will pick up in RUNNING mode).

## RUNNING mode

Triggered when state.json exists and phase=running. This is the workhorse iteration body. Everything below is non-blocking — no AskUserQuestion calls, no human in the loop.

**Iteration error wrap (D2 LOCKED):** Treat the entire iteration body (Steps 2-8 below) as a single try-block. On ANY caught error from a sub-step (helper exit non-zero, prompt-driven path failing, state-update disk-write failing, etc.):

1. Append a timestamped error line to `$state_dir/last-iteration.log`.
2. Append a `## ITERATION ERROR — <class>` block to the research-log entry (or local notes fallback) with the error class + partial context.
3. `state-update` to bump `consecutive_iteration_failures` and set `last_error_at`:
   ```bash
   "$SKILL_DIR/bin/state-update" --slug "$slug" --set '
     .consecutive_iteration_failures += 1
     | .last_error_at = (now | todateiso8601)
   '
   ```
4. Do NOT set `phase=halted` — keep `phase=running` so the loop tries again.
5. Compute exponential backoff:
   ```bash
   n=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .consecutive_iteration_failures)
   # delay = min(3600, 1800 * 2^(n-1))
   delay=$(( 1800 * (1 << (n - 1)) ))
   [[ "$delay" -gt 3600 ]] && delay=3600
   ```
6. Call `ScheduleWakeup(prompt="/autoresearch", delaySeconds=$delay, reason="iteration error: <class>; backoff scheduled")`.
7. Exit cleanly.

On a **successful iteration** (Step 5 below), reset `.consecutive_iteration_failures = 0` in the same `state-update` call that records the result. Then proceed with normal pacing in Step 9.

### Step 1 — Check stop conditions

```bash
if [[ "$STOP_PRESENT" -eq 1 ]]; then
  STOP_REASON="STOP file present"
elif <target_metric reached>; then  # see Step 5 logic — current_best.metric_value satisfies target_metric
  STOP_REASON="target metric achieved"
elif <queue empty AND last 3 replans added no candidates>; then
  STOP_REASON="search space exhausted"
fi

if [[ -n "${STOP_REASON:-}" ]]; then
  # Write final summary, exit cleanly. Do NOT call ScheduleWakeup.
  ...  # see "Termination" section below
  exit 0
fi
```

### Step 2 — Pick next candidate

Read the highest-priority candidate from `state.candidate_queue` where status=pending. Mark it status=running.

```bash
"$SKILL_DIR/bin/state-update" --slug "$slug" \
  --set "(.candidate_queue[] | select(.id == \"$CAND_ID\") | .status) = \"running\" | .iteration_count += 1"
```

### Step 3 — Run the experiment

The skill does NOT prescribe how to invoke the user's training/eval — that comes from project context (CLAUDE.md should have it, or the LLM infers from the project README/Makefile). Capture stdout+stderr to `last-iteration.log` in the state dir.

```bash
log="$state_dir/last-iteration.log"
# Example invocation; the LLM materializes the actual command from project context + the candidate's axes
{ <user's training command with axes substituted> ; } > "$log" 2>&1
exit_code=$?
```

If `exit_code == 0`, parse the metric from the log (the LLM extracts it; the format depends on the project — usually a known stdout pattern or a metrics JSON written by the run).

### Step 4 — Handle failure (if any)

If `exit_code != 0`, apply the failure pipeline:

1. Apply the prompt at `prompts/error-classification.md` with `last-iteration.log` as input.
2. Read the classification:
   - `class=transient`: retry the same candidate up to 3 times total with the suggested adjustment. If still failing, treat as code_bug. Reset `.consecutive_infra_count` (D4) on retry success.
   - `class=code_bug`: stash → fix → rerun. Up to 3 fix attempts (D1 LOCKED stash discipline).
     - Each attempt:
       ```bash
       STASH_REF=$("$SKILL_DIR/bin/stash-and-fix-prep")
       "$SKILL_DIR/bin/state-update" --slug "$slug" --set ".pending_stash_ref = \"$STASH_REF\""
       # apply LLM-proposed Edit on $FIX_TARGET_FILE
       # rerun the experiment
       ```
     - **On rerun success:**
       - `commit-experiment` commits the fix + any other uncommitted state
       - `if [[ "$STASH_REF" != "__CLEAN__" ]]; then git stash drop "$STASH_REF"; fi` (clean up the orphan)
       - Clear `pending_stash_ref` and reset `consecutive_infra_count` to 0.
     - **On rerun failure:**
       - `git checkout -- "$FIX_TARGET_FILE"` (revert bad edit; safe because Code-Fix prompt restricts edits to a single existing file). Run this BEFORE the stash pop.
       - `if [[ "$STASH_REF" != "__CLEAN__" ]]; then git stash pop "$STASH_REF"; fi` (restore prior uncommitted work)
       - Try a different fix; mark candidate dead after 3 attempts. Clear `pending_stash_ref` after each loop iteration.
   - `class=infrastructure`: apply the **D4 consecutive-infra-count gate**:
     ```bash
     candidates_so_far=$("$SKILL_DIR/bin/state-read" --slug "$slug" \
       --path '.consecutive_infra_candidates')
     if echo "$candidates_so_far" | jq -e --arg id "$CAND_ID" 'index($id)' >/dev/null; then
       # Same candidate already counted — treat as unknown/skip, do NOT increment.
       :
     else
       "$SKILL_DIR/bin/state-update" --slug "$slug" --set "
         .consecutive_infra_count += 1
         | .consecutive_infra_candidates += [\"$CAND_ID\"]
       "
     fi
     count=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .consecutive_infra_count)
     if [[ "$count" -ge 2 ]]; then
       # HALT: write final summary with ## INFRASTRUCTURE FAILURE block, set phase=halted, do NOT ScheduleWakeup.
       ...
       exit 0
     else
       # Skip current candidate, continue loop.
       :
     fi
     ```
   - `class=unknown`: log + skip + continue. Do NOT update infra counters.

**Reset rule (D4 LOCKED):** On any non-infra outcome (transient retry succeeded, code-fix succeeded, complete result), set `consecutive_infra_count = 0` and `consecutive_infra_candidates = []` in the same state-update call that records the result.

### Step 5 — Update state with result

On success or recovery:

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$SKILL_DIR/bin/state-update" --slug "$slug" --set "
  .results_history += [{
    id: \"$CAND_ID\",
    axes: $AXES_JSON,
    started_at: \"$STARTED_AT\",
    ended_at: \"$NOW\",
    status: \"$STATUS\",  # complete | fixed | failed
    metric_value: $METRIC_VALUE,
    fix_attempts: $FIX_ATTEMPTS,
    error_class: $ERROR_CLASS,
    commit_sha: \"$COMMIT_SHA\",
    notes: \"\",
    iteration_runtime_seconds: $RUNTIME_SECONDS,
    llm_call_count_estimate: $LLM_CALL_COUNT
  }]
  | .last_iteration_completed_at = \"$NOW\"
  | .consecutive_iteration_failures = 0
  | .consecutive_infra_count = 0
  | .consecutive_infra_candidates = []
"

# Update current_best if applicable (per target_metric.op direction)
```

`$LLM_CALL_COUNT` is the count of LLM-driven sub-steps within this iteration (replan, error-classification, code-fix, etc.). Increment it as you go through Steps 3-7; surface the running tally here. The user can sum across `results_history` to estimate session token cost (folded fix #1).

### Step 6 — Adaptive replan

Apply the prompt at `prompts/adaptive-replan.md` with the full state.json + just-completed iteration result. Output JSON:
- `next_candidate` (or null if exhausted)
- `queue_updates` (add/remove/reprioritize)
- `pivot` flag and reason
- `log_block` (3-5 line markdown for live append)
- `promote_to_result_block` (full ## RESULT block if meaningful, else "")

Apply queue_updates to state.candidate_queue. Append pivot to pivot_history if pivot.happened.

### Step 7 — Append to research-log entry

```bash
session_path=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .research_log.session_path)
log_available=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .research_log.available)

block=""
[[ -n "${PIVOT_REASON:-}" ]] && block+="## PIVOT — $PIVOT_REASON

"
block+="$LOG_BLOCK

"
[[ -n "${RESULT_BLOCK:-}" ]] && block+="$RESULT_BLOCK
"

if [[ "$log_available" == "true" ]]; then
  printf "%s" "$block" | "$SKILL_DIR/bin/research-log-append" \
    --file "$session_path" \
    --commit-message "autoresearch: iter $ITER — $LOG_SUMMARY"
else
  printf "%s" "$block" | "$SKILL_DIR/bin/notes-append-local" --slug "$slug"
fi
```

### Step 8 — Commit project repo

```bash
"$SKILL_DIR/bin/commit-experiment" \
  --scope-slug "$SCOPE_SLUG" \
  --iter "$ITER" \
  --candidate "$CAND_ID" \
  --message-suffix "metric=$METRIC_VALUE"
```

### Step 9 — Schedule next iteration

```
ScheduleWakeup(
  delaySeconds=<adaptive — see below>,
  prompt="/autoresearch",
  reason="iter $ITER complete; iter $((ITER+1)) scheduled"
)
```

**Adaptive pacing**: `delaySeconds = max(60, last_iteration_runtime_seconds * 0.05)`. If iterations are taking 30 minutes, sleep ~90s between. If they're taking 30 seconds, sleep 60s (the floor — don't hammer rate limits).

After ScheduleWakeup returns, exit. Done with this iteration.

## Termination

When a stop condition is hit (Step 1 of RUNNING mode), produce the final summary and exit WITHOUT calling ScheduleWakeup.

```bash
# Set phase based on stop reason
case "$STOP_REASON" in
  "STOP file present")  PHASE_FINAL="cancelled" ;;
  "target metric achieved") PHASE_FINAL="completed" ;;
  "search space exhausted") PHASE_FINAL="completed" ;;
  *) PHASE_FINAL="halted" ;;
esac

NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
"$SKILL_DIR/bin/state-update" --slug "$slug" \
  --set ".phase = \"$PHASE_FINAL\" | .stop_reason = \"$STOP_REASON\" | .last_iteration_completed_at = \"$NOW\""

# Compose final summary block via LLM, append to log
final_block="## Final Summary

Stop reason: $STOP_REASON
Iterations: $ITER
Best: $BEST_AXES → $BEST_METRIC_VALUE
Pivots: $PIVOT_COUNT
Time: $SESSION_DURATION

<LLM-generated narrative summary, 5-10 lines>
"

if [[ "$log_available" == "true" ]]; then
  printf "%s" "$final_block" | "$SKILL_DIR/bin/research-log-append" \
    --file "$session_path" \
    --commit-message "autoresearch: session complete — $STOP_REASON"
else
  printf "%s" "$final_block" | "$SKILL_DIR/bin/notes-append-local" --slug "$slug"
fi
```

## Question deferral mailbox

Whenever the LLM hits a decision it can't confidently make and would normally ask the user (e.g., "this result is surprising; should we expand scope?"), instead append to `$state_dir/QUESTIONS_FOR_USER.md`:

```bash
{
  echo ""
  echo "## $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo ""
  echo "**Context:** <one paragraph>"
  echo ""
  echo "**Question:** <the question>"
  echo ""
  echo "**Best guess used:** <what we did>"
} >> "$state_dir/QUESTIONS_FOR_USER.md"
```

Then continue with the best guess. NEVER block on a question post-launch.
