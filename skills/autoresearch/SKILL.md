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
