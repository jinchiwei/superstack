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
  # Capture exit code without tripping `set -e` (the script may run under
  # `set -euo pipefail` in the harness).
  validate_status=0
  "$SKILL_DIR/bin/state-validate" --slug "$slug" || validate_status=$?
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

### Step 2.5 — Literature review (research scopes only)

Run a focused literature review **before** axis enumeration so axes can be informed by what's been tried, and so the user sees the novelty case in Step 4 alongside the proposed sweep.

**Stage A — classify + propose queries.** Apply `prompts/lit-review-classify.md` with:
- `scope`: the scope text
- `project_context`: a brief summary of what was read in Step 2

The output is one of:
- `{"skip": true, "reason": "..."}` — non-research scope (QA automation, build matrix, ops sweep, etc.). Set `$LIT_REVIEW_AVAILABLE=false`, write `$state_dir/lit-review-skipped.txt` with the reason, and proceed to Step 3 (axis enumeration runs without lit context).
- `{"queries": [...], "sources": [...], "focus": "..."}` — proceed to Stage B.

**Stage B — fetch abstracts.** For each query, invoke:

```bash
"$SKILL_DIR/bin/lit-search" \
  --query "$Q" \
  --max-results 8 \
  --source "$(echo "$SOURCES" | tr ' ' ,)" \
  > "$state_dir/lit-papers-$i.json"
```

Concatenate and de-duplicate by `url` across queries. Save the merged list to `$state_dir/lit-papers.json`. Per-query `bin/lit-search` failures are non-fatal; the script handles partial failures gracefully (e.g., a Semantic Scholar 429 leaves PubMed + arXiv results intact).

If the merged list is empty after all queries, set `$LIT_REVIEW_AVAILABLE=true` but with the empty-result handling path (the synthesizer still runs and returns a "no comparable prior work" framing).

**Stage C — synthesize.** Apply `prompts/lit-review-synthesize.md` with:
- `scope`, `focus` (from Stage A), `project_context`, `papers` (merged list)

Save the synthesis to `$state_dir/lit-review.json` and a human-readable `$state_dir/lit-review.md`. Surface the `axis_implications` field into Step 3 as additional context.

**Failure modes:** if Stage A errors (LLM returns malformed JSON), retry once. If it fails again, set `$LIT_REVIEW_AVAILABLE=false` and proceed without lit review (do NOT block the session). If Stage C errors, save raw papers but proceed without synthesis. Lit review is **non-essential** — never block axis enumeration on a lit-review failure.

### Step 3 — Enumerate axes via the LLM

Apply the prompt at `prompts/axis-enumeration.md` with:
- `scope`: the scope text
- `project_context`: a brief summary of what you read
- `lit_review_summary` (optional): the `axis_implications` field from Step 2.5 if `$LIT_REVIEW_AVAILABLE=true`. Pass an empty string otherwise.

Produce the JSON with `scope_slug`, `target_metric`, `axes`, `rationale`.

If the LLM returns `{"error": ...}`, surface the error to the user via AskUserQuestion: "Scope didn't parse — <reason>. Provide a clearer scope or cancel?" Then either re-attempt with the new scope or exit with phase=cancelled.

### Step 4 — Show planned axes + ask user to confirm

This is the **only blocking AskUserQuestion in the entire skill workflow.** Pre-launch, before walking away. After this, the no-questions invariant kicks in.

Use AskUserQuestion with the rendered plan. When `$LIT_REVIEW_AVAILABLE=true`, include the lit-review block above the axes; when skipped, include a one-liner naming the skip reason; when unavailable due to failure, omit the block entirely.

```
Plan: <scope_slug>
Target: <target_metric or "no explicit target — stop on exhaustion">

Lit review: <N queries, M abstracts; top relevance: <top_relevant[0].title>>
  Prior work: <prior_work_summary, 1-2 lines>
  Novelty: <novelty_argument, 1 line>
  [or] Lit review skipped — <reason>
  [or] (block omitted on failure)

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
- **D) Override lit-review classification** — only show this option when the classifier ran (skipped or proceeded). Lets the user flip the decision: if proceeded, mark as skipped; if skipped, force a re-classify with a hint. Re-loops to Step 2.5.

### Step 5 — Initialize state.json

Build the candidate queue from the Cartesian product of axes. Random shuffle within priority groups (later replans will reweight).

```bash
# Pipe an axes JSON to state-init
echo "$AXES_JSON" | "$SKILL_DIR/bin/state-init" --slug "$slug"
"$SKILL_DIR/bin/state-update" --slug "$slug" \
  --argjson queue "$QUEUE_JSON" \
  --set '.candidate_queue = $queue | .phase = "running"'
```

### Step 5b — Initialize project layout + session README

If this is the first autoresearch session in the project (no `exp/` or `results/` dirs yet), bootstrap the layout. Idempotent — skips existing files.

```bash
"$SKILL_DIR/bin/init-project"
# Then write the session dashboard
TODAY=$(date -u +%Y%m%d)
"$SKILL_DIR/bin/session-readme" init \
  --scope-slug "$SCOPE_SLUG" \
  --scope-text "$SCOPE_TEXT" \
  --target "$TARGET_DESCRIPTION" \
  --axes-json "$AXES_JSON" \
  --date "$TODAY"
```

`init-project` creates `exp/`, `results/`, `docs/`, adds `exp/` to `.gitignore`, and drops branded `_build_pptx.py` / `_build_pdf.py` / `_build_docx.py` / `_build_xlsx.py` templates into `docs/`. The user can edit those freely — autoresearch invokes them at termination if present.

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
    --arg entry "$ENTRY" \
    --set '.research_log.available = true | .research_log.session_path = $entry'
else
  fallback="$home/projects/$slug/autoresearch/notes.md"
  "$SKILL_DIR/bin/state-update" --slug "$slug" \
    --arg fallback "$fallback" \
    --set '.research_log.available = false | .research_log.fallback_path = $fallback'
  printf "%s\n" "$INITIAL_ENTRY_BODY" | "$SKILL_DIR/bin/notes-append-local" --slug "$slug"
fi
```

`$INITIAL_ENTRY_BODY` is rendered by the LLM following the existing research-log format rules (h1 title, structured blurb on line 3, Date / Project / Status block, Why, Plan, Axes, Target).

When `$LIT_REVIEW_AVAILABLE=true`, insert a `## Prior work & novelty` section between `## Why` and `## Plan`. Render it from `$state_dir/lit-review.json` produced in Step 2.5. Format:

```markdown
## Prior work & novelty

**Prior work:** {prior_work_summary}

**Dominant approaches in the literature:**
- {dominant_approaches[0]}
- {dominant_approaches[1]}
- ...

**Gaps:**
- {gaps[0]}
- {gaps[1]}
- ...

**Novelty argument:** {novelty_argument}

**Top relevant prior work:**
1. [{top_relevant[0].title}]({top_relevant[0].url}) ({top_relevant[0].year}) — {top_relevant[0].why_relevant}
2. ...
```

Skip the section entirely when `$LIT_REVIEW_AVAILABLE=false` (research-log entry has Why → Plan → Axes → Target as before). Do not write a "Lit review skipped" placeholder; absence is the signal. The skip reason is captured in `$state_dir/lit-review-skipped.txt` for later reference if needed.

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

**What the wrap covers — and what it does NOT:** The wrap is for **infrastructure errors in the iteration body** (helper exits non-zero, jq parse failure on LLM-produced JSON, state-update disk-write failure, etc). It is **NOT** for the experiment command itself. The experiment's non-zero exit code is *expected data* that flows into Step 4's classifier (transient / code_bug / infrastructure / unknown). If you `||`-gate the experiment to `on_iteration_error`, ordinary candidate failures bypass the classifier and the candidate stays marked `running` while the loop just backs off — exactly the failure mode D2 + D4 were designed to prevent.

**Concrete try-block pattern (bash has no native try):** Bash doesn't have try/catch. Use one of two patterns. Either (preferred for an explicit list of steps) gate **non-experiment** helper calls with `||`, and capture the experiment's exit code without gating it:

```bash
# At the top of the iteration body
on_iteration_error() {
  local err_class="${1:-unknown}"
  local err_context="${2:-}"
  echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] iteration error: $err_class: $err_context" >> "$state_dir/last-iteration.log"
  # ...append research-log block, bump counters, compute backoff, ScheduleWakeup, exit 0...
  exit 0
}

# Helper steps are gated. Any non-zero from these is an infrastructure failure of the wrap.
"$SKILL_DIR/bin/state-update" --slug "$slug" --arg id "$CAND_ID" \
  --set '(.candidate_queue[] | select(.id == $id) | .status) = "running" | .iteration_count += 1' \
  || on_iteration_error state_update "marking candidate running"

# The experiment is NOT ||-gated. Its exit code is expected signal for Step 4.
log="$state_dir/last-iteration.log"
{ <user's training command with axes substituted> ; } > "$log" 2>&1
exit_code=$?  # This drives Step 4's failure pipeline if non-zero.

# After Step 4 runs (and either retries / code-fixes / records failure), continue to:
"$SKILL_DIR/bin/state-update" --slug "$slug" ... \
  || on_iteration_error state_update "recording result"
# ... etc for each remaining helper step
```

Or (preferred when you want a single trap covering the whole body) use `trap ... ERR` plus `set -e`, with the experiment command exempted:

```bash
set -eE
trap 'on_iteration_error trap "step exited non-zero"' ERR

# Steps 2 helpers here under the trap.

# Disable the trap around the experiment. Non-zero is expected signal, not error.
set +e; trap - ERR
{ <user's training command with axes substituted> ; } > "$log" 2>&1
exit_code=$?
# Step 4 failure pipeline runs here based on exit_code (no trap).

# Re-arm the trap for Steps 5-8 helpers.
set -eE
trap 'on_iteration_error trap "step exited non-zero"' ERR

# ... Steps 5-8 ...
trap - ERR  # clear once Step 8 completes
```

The `||` form is more explicit and easier to debug; the `trap ERR` form is more compact. Pick one and use it consistently. **Do NOT** mix patterns. **Do NOT** leave bash unconfigured (no `set -e` and no `||` gates) — silent error pass-through is the failure mode the wrap was designed to prevent. **Do NOT** route the experiment command into `on_iteration_error` — its exit code is consumed by Step 4.

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
  --arg id "$CAND_ID" \
  --set '(.candidate_queue[] | select(.id == $id) | .status) = "running" | .iteration_count += 1'
```

### Step 2.5 — Compute output dirs + export env vars

Before running the experiment, compute the standard `results/` and `exp/` paths for this iteration and export them so the candidate's command can write outputs there.

```bash
TODAY=$(date -u +%Y%m%d)
SCOPE_SLUG=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .scope_slug)

# Candidate slug: short, filename-safe ID for this candidate (e.g. its axes condensed).
# Prefer the candidate's own .slug if state.json carries one; else derive from CAND_ID.
CAND_SLUG=$("$SKILL_DIR/bin/state-read" --slug "$slug" \
  --path ".candidate_queue[] | select(.id == \"$CAND_ID\") | .slug // .id")

export AUTORESEARCH_OUT_RESULTS=$("$SKILL_DIR/bin/results-dir" \
  --scope-slug "$SCOPE_SLUG" --iter "$ITER" --candidate-slug "$CAND_SLUG" --date "$TODAY")
export AUTORESEARCH_OUT_EXP=$("$SKILL_DIR/bin/exp-dir" \
  --scope-slug "$SCOPE_SLUG" --iter "$ITER" --candidate-slug "$CAND_SLUG" --date "$TODAY")
```

Both env vars are absolute-or-relative paths to dirs that already exist (the helpers `mkdir -p` them). The candidate's command MUST honor them — see Step 3.

### Step 3 — Run the experiment

The skill does NOT prescribe how to invoke the user's training/eval — that comes from project context (CLAUDE.md should have it, or the LLM infers from the project README/Makefile). The materialized command MUST write its outputs into `$AUTORESEARCH_OUT_RESULTS` (synthesized: figures, csv, `summary.md`) and `$AUTORESEARCH_OUT_EXP` (raw: checkpoints, big intermediate files). The skill propagates these env vars; the LLM is responsible for using them in the command it constructs.

Capture stdout+stderr to `last-iteration.log` in the state dir.

```bash
log="$state_dir/last-iteration.log"
# Example invocation; the LLM materializes the actual command from project context + the candidate's axes.
# Inside the command, scripts read $AUTORESEARCH_OUT_RESULTS / $AUTORESEARCH_OUT_EXP for output paths.
{ <user's training command with axes substituted> ; } > "$log" 2>&1
exit_code=$?
```

After the command, the skill REQUIRES that `$AUTORESEARCH_OUT_RESULTS/summary.md` was written. If missing, treat as an iteration failure (class=infrastructure) — the candidate didn't produce its required artifact.

If `exit_code == 0` AND `summary.md` exists, parse the metric from the log or from `summary.md` (the LLM extracts it; the format depends on the project — usually a known stdout pattern or a metrics JSON written by the run).

**Figure contract (STRONGLY RECOMMENDED):** every phase script SHOULD also write at least one `fig_*.png` (e.g. `fig_roc.png`, `fig_calibration.png`, `fig_strata_forest.png`) into `$AUTORESEARCH_OUT_RESULTS`. The deck builder (`_build_pptx.py`) auto-discovers and embeds every `fig_*.png` it finds under `iter-*/` — so any figure the experiment produces lands on its own slide in the session report. Sessions that skip figures get text-only decks; reviewers will ask. When generating an experiment driver, default to plotting an ROC + calibration curve for any classification phase; an AUC-by-stratum forest plot for any subgroup phase; and an OOF/preds save (e.g. `oofs.npz`) so plots can be regenerated later without re-running training.

### Step 4 — Handle failure (if any)

If `exit_code != 0`, apply the failure pipeline:

1. Apply the prompt at `prompts/error-classification.md` with `last-iteration.log` as input.
2. Read the classification:
   - `class=transient`: retry the same candidate up to 3 times total with the suggested adjustment. If still failing, treat as code_bug. Reset `.consecutive_infra_count` (D4) on retry success.
   - `class=code_bug`: stash → fix → rerun. Up to 3 fix attempts (D1 LOCKED stash discipline).
     - Each attempt:
       ```bash
       STASH_REF=$("$SKILL_DIR/bin/stash-and-fix-prep")
       "$SKILL_DIR/bin/state-update" --slug "$slug" \
         --arg ref "$STASH_REF" \
         --set '.pending_stash_ref = $ref'
       # apply LLM-proposed Edit on $FIX_TARGET_FILE
       # rerun the experiment
       ```
     - **On rerun success:**
       - `commit-experiment` commits ONLY the fix that the LLM applied to the clean tree (the user's prior dirty state is still inside the stash at this point — it MUST be preserved).
       - Set `EXPERIMENT_ALREADY_COMMITTED=1` (a local shell flag for this iteration). Step 8 below checks this flag and skips its own `commit-experiment` call to avoid sweeping the about-to-be-popped user work into the same iteration commit.
       - `if [[ "$STASH_REF" != "__CLEAN__" ]]; then git stash pop "$STASH_REF"; fi` — restore the user's pre-existing uncommitted work into the working tree. **Do NOT use `git stash drop` here.** Dropping discards user work that wasn't part of the fix. (The popped work stays uncommitted on top of the fix commit; eventual sweep happens at the next regular iteration's Step 8 per the documented gotcha in USAGE.md, OR the user can resolve it before then.)
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
       "$SKILL_DIR/bin/state-update" --slug "$slug" \
         --arg id "$CAND_ID" \
         --set '
           .consecutive_infra_count += 1
           | .consecutive_infra_candidates += [$id]
         '
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
   - `class=unknown`: log + skip + continue. **Reset infra counters** here too — the unknown skip is a non-infra terminal outcome, so it breaks the "consecutive infra" chain (otherwise infra → unknown → infra would HALT despite being non-consecutive).

**Reset rule (D4 LOCKED):** On any non-infra terminal outcome (transient retry succeeded, code-fix succeeded, complete result, **or unknown skip**), set `consecutive_infra_count = 0` and `consecutive_infra_candidates = []`. For complete/recovery results this happens in the Step 5 state-update; for transient retry success and unknown skips, do an explicit state-update at the point of the outcome.

### Step 5 — Update state with result

On success or recovery:

```bash
NOW=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Build the result entry as JSON ahead of time so values flow through --argjson.
# This avoids embedding LLM-controlled strings ($CAND_ID, $ERROR_CLASS, $COMMIT_SHA) directly into the jq filter.
result_entry=$(jq -n \
  --arg id "$CAND_ID" \
  --argjson axes "$AXES_JSON" \
  --arg started "$STARTED_AT" \
  --arg ended "$NOW" \
  --arg status "$STATUS" \
  --argjson metric "${METRIC_VALUE:-null}" \
  --argjson fix_attempts "${FIX_ATTEMPTS:-0}" \
  --arg error_class "${ERROR_CLASS:-}" \
  --arg commit_sha "${COMMIT_SHA:-}" \
  --argjson runtime "${RUNTIME_SECONDS:-0}" \
  --argjson llm_calls "${LLM_CALL_COUNT:-0}" \
  '{
    id: $id, axes: $axes, started_at: $started, ended_at: $ended,
    status: $status, metric_value: $metric, fix_attempts: $fix_attempts,
    error_class: (if $error_class == "" then null else $error_class end),
    commit_sha: (if $commit_sha == "" then null else $commit_sha end),
    notes: "", iteration_runtime_seconds: $runtime, llm_call_count_estimate: $llm_calls
  }')

"$SKILL_DIR/bin/state-update" --slug "$slug" \
  --argjson entry "$result_entry" \
  --arg now "$NOW" \
  --set '
    .results_history += [$entry]
    | .last_iteration_completed_at = $now
    | .consecutive_iteration_failures = 0
    | .consecutive_infra_count = 0
    | .consecutive_infra_candidates = []
  '

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

### Step 7b — Append iteration row to session README

```bash
"$SKILL_DIR/bin/session-readme" append \
  --scope-slug "$SCOPE_SLUG" \
  --iter "$ITER" \
  --candidate-slug "$CAND_SLUG" \
  --status "$STATUS" \
  --metric "${METRIC_VALUE:-}" \
  --date "$TODAY"
```

This appends a row to `results/<date>_<scope>/README.md` — the at-a-glance session dashboard.

### Step 8 — Commit project repo

Skip if Step 4's code_bug success path already committed the fix — otherwise we'd sweep the just-popped user work into a second iteration commit (per /codex review P2-1).

```bash
if [[ "${EXPERIMENT_ALREADY_COMMITTED:-0}" -eq 1 ]]; then
  : # Step 4 already committed the fix; do not commit again here.
else
  "$SKILL_DIR/bin/commit-experiment" \
    --scope-slug "$SCOPE_SLUG" \
    --iter "$ITER" \
    --candidate "$CAND_ID" \
    --message-suffix "metric=$METRIC_VALUE"
fi
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

## Reporting conventions (canonical)

When this skill — or any project that produces a figure deliverable downstream of an autoresearch run — renders feature names or metric tables, the following rules are NON-NEGOTIABLE:

1. **Feature-direction / SHAP plots MUST use human-readable axis labels.** Pyradiomics raw column names like `log-sigma-2-0-mm-3D_glcm_Imc1` or `original_glcm_Idn` are unreadable on a slide. Always pass them through `superstack/skills/_shared/feature_naming.py::clean_radiomic_feature_name` before rendering. The helper expands matrix abbreviations (GLCM → "Co-occurrence", GLRLM → "Run-length", etc.) and feature-name shorthand (Imc1 → "Information Measure of Correlation 1", Idn → "Inverse Difference Normalized"), and renders the image filter as a parenthetical suffix.

2. **Metric leaderboard tables (matplotlib) MUST size column widths to content.** matplotlib's default `Table` gives every column equal width — long pipeline names get visually truncated while short numeric columns waste space. Always pass `colWidths=` computed via `superstack/skills/_shared/plotting_helpers.py::proportional_col_widths(rows, headers)`.

Both helpers are zero-dependency and import-safe; project code should add `superstack/skills/_shared` to `sys.path` and import them directly.

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
  --arg phase "$PHASE_FINAL" \
  --arg reason "$STOP_REASON" \
  --arg now "$NOW" \
  --set '.phase = $phase | .stop_reason = $reason | .last_iteration_completed_at = $now'

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

### Generate session reports

After the final summary is written, invoke any project-local doc builders to produce a shareable session report. Each builder is called with the standard `--date` + `--scope` args and writes to `results/<date>_<scope>/` (e.g. `SESSION_REPORT.{pptx,pdf,docx}`, `scorecard_<date>.xlsx`). The default `_build_pptx.py` template synthesizes a markdown deck — auto-embedding every `fig_*.png` it finds in iter dirs — and shells out to the `build-pptx` skill, so the deck inherits that skill's full layout catalog and branding.

**Deck synthesis: read build-pptx's SKILL.md FIRST.** Before authoring or modifying `templates/_build_pptx.py`, read `skills/build-pptx/SKILL.md` and `skills/build-pptx/tests/fixture_realistic.md` end-to-end. Critical structural rules that are easy to miss:

- `# H1` between `---` separators auto-emits a **section-divider slide** (navy background, large title) — H1s are NOT regular content titles. Use them only for top-level sections (Background, Methods, Results, Conclusions, Iteration detail).
- `## H2` is for content slides under the previous H1's section. Each H2 should have substantive content (multiple sentences, a table, a figure, or a card list) — never a one-line slide.
- Section accent colors auto-propagate from H1 → all content slides under it via `branding.match_section_color`. Use canonical section names (Background / Methods / Results / Conclusions / Limitations / Validation / etc) to inherit the correct turquoise / deeppink / amber / blueviolet palette.
- Frontmatter `name:` and `org:` populate the auto-cover byline. The autoresearch synthesizer reads these from `~/.gstack/superstack/author.json` (or `$AUTORESEARCH_AUTHOR_NAME` / `$AUTORESEARCH_AUTHOR_ORG`) so deck attribution is consistent across projects.
- `findings.md` in the session root, if present, replaces the auto-generated Background+Methods+Results+Conclusions block. Iteration-detail slides are always auto-generated.

A regression test in `tests/test_build_pptx.py` verifies the synthesizer emits H1 dividers + dense content slides — do not break it.

**Handcraft the session deck yourself — don't stop at the shell-out.** build-pptx runs an expressive-freeform composer by default, so the non-interactive shell-out produces a deterministic floor of designed freeform slides (never bare named layouts). But that floor is generic/template-like. **You (the autoresearch agent) are an agent in the loop, so you MUST handcraft the session deck — this is required, not optional polish.** After the shell-out writes the `.layout.json` sidecar, follow **`skills/build-pptx/bespoke_design.md`**: handcraft each content slide's composition from scratch for its actual content, following NOTHING except the brand lock (Geist fonts + brand-4 accents + section-cycled colorbar). Do NOT pick from a catalog or force every slide into one mold — design each for its content (coincidental resemblance between genuinely-similar slides is fine; mechanical template-following is not). Write the handcrafted freeform entries back into the sidecar before the final render.

**Generate custom intro / background figures — this is the autoresearch default.** Report decks for an external or cold audience need ≥ 3 background slides BEFORE methods/results, and each background slide needs a custom matplotlib figure that **redraws a foundational reference** with clear "(adapted from Author Year)" attribution — never a placeholder slot and never a screenshotted paper figure. Follow **`skills/build-pptx/intro_figures.md`** for the pattern, archetype catalog (biomarker cascade, decomposition schematic, dose-response bars, ATN-style framework boxes, pipeline flowchart, cohort matrix), and the reference implementation. Write a `docs/runs/<date>_<scope>/_make_figs.py` that generates `figures/intro_*.png` + `figures/methods_*.png` using `_shared/mpl_style` brand styling, with the citation embedded in each figure's title via `title(ax, "... (Author Year, Journal)")`. The deck.md's `![alt](figures/intro_xyz.png)` references then become rich, on-brand intro slides instead of bullet walls. Cite only real primary sources from your training; never fabricate.

**Use the reusable figure archetypes from `skills/_shared/deck_figures.py`** rather than hand-rolling matplotlib for every results scorecard. The catalog (`skills/build-pptx/figure_archetypes.md`) includes 4-panel composite scorecards, region-dot strips, comparison-bar pairs, AIC sweeps, FDR survival grids, depth schematics, compartment partitions, and pipeline flows. Each is one function call with brand-locked styling baked in. The default for any methods/results slide is a figure built from one of these archetypes, not a typed table of numbers. A typed table is a fallback only when no archetype fits — and if you find yourself wanting the same custom figure across two sessions, promote it into `deck_figures.py` per the doc's "Adding new archetypes" section.

```bash
SESSION_DATE=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .session_started_at | cut -dT -f1)
[[ -z "$SESSION_DATE" || "$SESSION_DATE" == "null" ]] && SESSION_DATE=$(date -u +%Y-%m-%d)

for builder in docs/_build_pptx.py docs/_build_docx.py docs/_build_pdf.py docs/_build_xlsx.py; do
  if [[ -f "$builder" ]]; then
    python "$builder" --date "$SESSION_DATE" --scope "$SCOPE_SLUG" \
      || echo "warning: $builder failed (continuing — reports are best-effort)"
  fi
done
```

**`_build_pptx.py` WILL fail the first time — that is the forcing function, not a real failure.** By design it no longer passes `--allow-composed`, so build-pptx's bespoke gate aborts on the agentless composer FLOOR and writes the scaffold sidecar but no `.pptx`. The "best-effort, continuing" branch above logs it — but **the session is NOT done until you, the agent in the loop, handcraft the deck.** Do NOT accept a missing or floor `SESSION_REPORT.pptx`: open the scaffold `results/<date>_<scope>/_deck.md.layout.json`, handcraft every content slide's freeform `code` per **`skills/build-pptx/bespoke_design.md`** (set `_provenance="agent"`), generate the theme-matched custom figures per `intro_figures.md`, then re-render with `build.py` (no `--allow-composed`) and self-QA the rasterized slides. Shipping the floor is the documented recurring failure this gate exists to stop. (A genuinely headless cron autoresearch run with no agent — and only that — may export `AUTORESEARCH_ALLOW_FLOOR_DECK=1` to ship the floor.)

The templates dropped by `init-project` honor this contract. If the project has its own opinionated builders (with different signatures), the user can either match the contract or replace this Step entirely. Report builds are best-effort — a builder failure does NOT prevent session termination.

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
