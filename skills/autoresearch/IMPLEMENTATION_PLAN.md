# /autoresearch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `/autoresearch` skill in `~/arcadia/superstack/skills/autoresearch/` so the user can invoke `/autoresearch "<scope>"` once and walk away — the skill self-paces multi-day autonomous research loops, persists state across sessions, optionally pushes to research-log, and fights through failures.

**Architecture:** Single-skill design (no separate daemon). SKILL.md is the main body; small bash helpers under `bin/` handle filesystem/state ops; prompt fragments under `prompts/` are loaded into SKILL.md sections. Self-paces via `ScheduleWakeup` tool at end of each iteration. State persists at `~/.gstack/projects/<slug>/autoresearch/`. Research-log integration is optional (auto-detect, fall back to local notes).

**Tech Stack:** Bash (helpers, bats tests), markdown (skill prose), `jq` (state.json manipulation), Claude Code tools (`ScheduleWakeup`, `AskUserQuestion`, `Bash`, `Edit`, `Read`).

**Reference docs:**
- Design: `~/arcadia/superstack/skills/autoresearch/DESIGN.md` (read this first — it has all the rationale)
- Mirror: `~/.gstack/projects/jinchiwei-superstack/jiwei-main-design-20260430-140826.md`

---

## File Structure

```
~/arcadia/superstack/skills/autoresearch/
├── DESIGN.md                       # already exists — design rationale
├── IMPLEMENTATION_PLAN.md          # already exists — this file
├── README.md                       # NEW — short pointer to DESIGN.md + invocation
├── USAGE.md                        # NEW — invocation examples + state.json layout
├── SKILL.md                        # NEW — main skill body (frontmatter + flow)
├── bin/
│   ├── stop-check                  # NEW — exits 0 if STOP file present, 1 otherwise
│   ├── state-init                  # NEW — write initial state.json from axes JSON stdin
│   ├── state-read                  # NEW — read state.json field via jq path
│   ├── state-update                # NEW — update state.json field via jq
│   ├── state-validate              # NEW — schema validation; exits 1 if invalid
│   ├── slug-from-cwd               # NEW — compute project slug from cwd
│   ├── research-log-detect         # NEW — check if research-log is set up
│   ├── research-log-append         # NEW — append block to current session's log file
│   ├── research-log-init-entry     # NEW — create new research-log entry on first iter
│   ├── notes-append-local          # NEW — fallback: append to local notes.md
│   ├── commit-experiment           # NEW — commit project repo per successful iteration
│   └── stash-and-fix-prep          # NEW — git stash + record stash ref for code-fix
├── prompts/
│   ├── axis-enumeration.md         # NEW — parse free-text scope → structured axes
│   ├── adaptive-replan.md          # NEW — given results so far, what next?
│   ├── error-classification.md     # NEW — transient / code-bug / infrastructure?
│   └── code-fix.md                 # NEW — propose Edit on failing line
└── tests/
    ├── helpers.bash                # NEW — bats test helpers
    ├── stop-check.bats             # NEW — tests for stop-check
    ├── slug-from-cwd.bats          # NEW
    ├── research-log-detect.bats    # NEW
    ├── state-roundtrip.bats        # NEW — init/read/update/validate cycle
    └── commit-experiment.bats      # NEW
```

---

## state.json schema (v1)

This is the contract every helper and every part of SKILL.md depends on. Lock it before writing anything.

```json
{
  "schema_version": 1,
  "session_id": "ar-2026-04-30-1000",
  "session_started_at": "2026-04-30T10:00:00Z",
  "last_iteration_at": "2026-04-30T14:30:00Z",
  "phase": "planning|running|halted|completed|cancelled",

  "scope": "iterate over architectures, input modes, loss functions for the FW prediction model",
  "scope_slug": "fw-architecture-sweep",
  "target_metric": {"name": "val_corr", "op": ">=", "threshold": 0.85},

  "axes": {
    "arch": ["unet", "transformer", "mlp"],
    "input": ["t1", "t2", "dwi"],
    "loss": ["mse", "smoothl1"]
  },
  "candidate_queue": [
    {"id": "c001", "axes": {"arch": "unet", "input": "t1", "loss": "mse"}, "status": "pending", "priority": 1.0}
  ],

  "results_history": [
    {
      "id": "c001",
      "axes": {"arch": "unet", "input": "t1", "loss": "mse"},
      "started_at": "2026-04-30T10:05:00Z",
      "ended_at": "2026-04-30T10:42:00Z",
      "status": "complete|failed|fixed|halted",
      "metric_value": 0.72,
      "fix_attempts": 0,
      "error_class": null,
      "commit_sha": "abc123",
      "notes": ""
    }
  ],
  "current_best": {"id": "c012", "metric_value": 0.81, "axes": {...}},

  "pivot_history": [
    {"at": "2026-04-30T15:00:00Z", "from_category": "arch", "to_category": "loss", "reason": "all archs converging at 0.78 — pivoting to loss tuning"}
  ],

  "research_log": {
    "available": true,
    "session_path": "~/arcadia/research-log/brainlab/ad-genetics-fwf/2026-04-30_autoresearch-fw-architecture-sweep.md",
    "fallback_path": null
  },

  "iteration_count": 12,
  "stop_reason": null
}
```

**Phase transitions:**
- New invocation, no state.json → `planning` → user confirms → `running`
- `running` → `running` (each iteration)
- `running` → `completed` (target hit / queue exhausted)
- `running` → `halted` (infra failure)
- `running` → `cancelled` (STOP file or user cancels at plan-confirm)

---

## TDD strategy

- **Bash helpers**: bats tests, one .bats file per helper. Tests cover happy path + 1-2 edge cases.
- **Prompt files**: no unit tests. Validated via the calibration run at the end of the plan.
- **SKILL.md prose**: no unit tests. Calibration run validates end-to-end.
- **State schema**: tested via the `state-roundtrip.bats` (init → read → update → validate cycle).

---

## Tasks

### Task 1: Create skill directory layout + commit baseline

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/`
- Create: `~/arcadia/superstack/skills/autoresearch/prompts/`
- Create: `~/arcadia/superstack/skills/autoresearch/tests/`

- [ ] **Step 1: Create dirs**

```bash
cd ~/arcadia/superstack
mkdir -p skills/autoresearch/{bin,prompts,tests}
```

- [ ] **Step 2: Confirm DESIGN.md and IMPLEMENTATION_PLAN.md already exist**

```bash
ls -la skills/autoresearch/DESIGN.md skills/autoresearch/IMPLEMENTATION_PLAN.md
```

Expected: both files listed, non-zero size.

- [ ] **Step 3: Verify bats is available for tests**

```bash
which bats || echo "MISSING — install via: bun add -g bats or apt install bats"
```

If bats is missing, install it. The test harness depends on it.

- [ ] **Step 4: Commit the dir scaffold**

```bash
cd ~/arcadia/superstack
git add skills/autoresearch/
git commit -m "feat(autoresearch): scaffold skill directory with DESIGN.md + IMPLEMENTATION_PLAN.md"
```

---

### Task 2: Write tests/helpers.bash

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/tests/helpers.bash`

- [ ] **Step 1: Write the helpers file**

```bash
# tests/helpers.bash
# Common setup/teardown for bats tests.

setup() {
  # Each test runs in an isolated temp dir
  TEST_DIR=$(mktemp -d)
  export TEST_DIR
  export FAKE_GSTACK_HOME="$TEST_DIR/gstack"
  export FAKE_PROJECT="$TEST_DIR/project"
  mkdir -p "$FAKE_GSTACK_HOME/projects/test-project/autoresearch" "$FAKE_PROJECT"
  cd "$FAKE_PROJECT" && git init -q && git commit --allow-empty -q -m "init"
  cd - >/dev/null
  export AUTORESEARCH_BIN="$BATS_TEST_DIRNAME/../bin"
  export GSTACK_HOME="$FAKE_GSTACK_HOME"
}

teardown() {
  rm -rf "$TEST_DIR"
}
```

- [ ] **Step 2: Commit**

```bash
git add skills/autoresearch/tests/helpers.bash
git commit -m "test(autoresearch): add bats helpers for isolated test dirs"
```

---

### Task 3: Implement bin/slug-from-cwd + tests

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/slug-from-cwd`
- Create: `~/arcadia/superstack/skills/autoresearch/tests/slug-from-cwd.bats`

- [ ] **Step 1: Write the failing test**

```bash
# tests/slug-from-cwd.bats
load helpers

@test "slug-from-cwd outputs basename of git toplevel" {
  cd "$FAKE_PROJECT"
  run "$AUTORESEARCH_BIN/slug-from-cwd"
  [ "$status" -eq 0 ]
  [ "$output" = "$(basename "$FAKE_PROJECT")" ]
}

@test "slug-from-cwd falls back to basename of cwd when not a git repo" {
  cd "$TEST_DIR"
  run "$AUTORESEARCH_BIN/slug-from-cwd"
  [ "$status" -eq 0 ]
  [ "$output" = "$(basename "$TEST_DIR")" ]
}
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd ~/arcadia/superstack/skills/autoresearch && bats tests/slug-from-cwd.bats
```

Expected: FAIL — slug-from-cwd not found.

- [ ] **Step 3: Implement**

```bash
#!/usr/bin/env bash
# bin/slug-from-cwd — print the project slug for the current working directory.
# Slug = basename of git toplevel; falls back to basename of cwd if not a git repo.
set -euo pipefail

if root=$(git rev-parse --show-toplevel 2>/dev/null); then
  basename "$root"
else
  basename "$PWD"
fi
```

- [ ] **Step 4: chmod + run tests to verify pass**

```bash
chmod +x skills/autoresearch/bin/slug-from-cwd
bats skills/autoresearch/tests/slug-from-cwd.bats
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/autoresearch/bin/slug-from-cwd skills/autoresearch/tests/slug-from-cwd.bats
git commit -m "feat(autoresearch): add slug-from-cwd helper + tests"
```

---

### Task 4: Implement bin/stop-check + tests

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/stop-check`
- Create: `~/arcadia/superstack/skills/autoresearch/tests/stop-check.bats`

- [ ] **Step 1: Write the failing tests**

```bash
# tests/stop-check.bats
load helpers

@test "stop-check exits 1 when STOP file is absent" {
  run "$AUTORESEARCH_BIN/stop-check" --slug test-project
  [ "$status" -eq 1 ]
}

@test "stop-check exits 0 when STOP file is present" {
  touch "$FAKE_GSTACK_HOME/projects/test-project/autoresearch/STOP"
  run "$AUTORESEARCH_BIN/stop-check" --slug test-project
  [ "$status" -eq 0 ]
}

@test "stop-check uses GSTACK_HOME env override" {
  GSTACK_HOME="$FAKE_GSTACK_HOME" run "$AUTORESEARCH_BIN/stop-check" --slug test-project
  [ "$status" -eq 1 ]
}
```

- [ ] **Step 2: Run to verify fail**

```bash
bats skills/autoresearch/tests/stop-check.bats
```

Expected: FAIL — stop-check not found.

- [ ] **Step 3: Implement**

```bash
#!/usr/bin/env bash
# bin/stop-check — exit 0 if the STOP file exists for the given slug, 1 otherwise.
# Usage: stop-check --slug <slug>
set -euo pipefail

slug=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) slug="$2"; shift 2 ;;
    *) echo "stop-check: unknown arg '$1'" >&2; exit 2 ;;
  esac
done

[[ -z "$slug" ]] && { echo "stop-check: --slug is required" >&2; exit 2; }

home="${GSTACK_HOME:-$HOME/.gstack}"
stop_file="$home/projects/$slug/autoresearch/STOP"
[[ -f "$stop_file" ]] && exit 0 || exit 1
```

- [ ] **Step 4: chmod + tests pass**

```bash
chmod +x skills/autoresearch/bin/stop-check
bats skills/autoresearch/tests/stop-check.bats
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/autoresearch/bin/stop-check skills/autoresearch/tests/stop-check.bats
git commit -m "feat(autoresearch): add stop-check helper + tests"
```

---

### Task 5: Implement state-init + state-read + state-update + state-validate

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/state-init`
- Create: `~/arcadia/superstack/skills/autoresearch/bin/state-read`
- Create: `~/arcadia/superstack/skills/autoresearch/bin/state-update`
- Create: `~/arcadia/superstack/skills/autoresearch/bin/state-validate`
- Create: `~/arcadia/superstack/skills/autoresearch/tests/state-roundtrip.bats`

- [ ] **Step 1: Write the failing tests**

```bash
# tests/state-roundtrip.bats
load helpers

@test "state-init creates state.json with required fields" {
  echo '{"scope":"test scope","scope_slug":"test","axes":{"a":["x","y"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  [ -f "$state_file" ]
  schema=$(jq -r .schema_version "$state_file")
  [ "$schema" = "1" ]
  phase=$(jq -r .phase "$state_file")
  [ "$phase" = "planning" ]
}

@test "state-read returns nested field via jq path" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  run "$AUTORESEARCH_BIN/state-read" --slug test-project --path .scope_slug
  [ "$status" -eq 0 ]
  [ "$output" = "sl" ]
}

@test "state-update modifies a field and increments iteration_count helper" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set '.phase = "running"'
  run "$AUTORESEARCH_BIN/state-read" --slug test-project --path .phase
  [ "$output" = "running" ]
}

@test "state-validate exits 0 on valid state, 1 on invalid" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  run "$AUTORESEARCH_BIN/state-validate" --slug test-project
  [ "$status" -eq 0 ]

  # corrupt the file
  echo "not json" > "$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  run "$AUTORESEARCH_BIN/state-validate" --slug test-project
  [ "$status" -eq 1 ]
}
```

- [ ] **Step 2: Run to verify fail**

```bash
bats skills/autoresearch/tests/state-roundtrip.bats
```

Expected: FAIL — none of the helpers exist.

- [ ] **Step 3: Implement state-init**

```bash
#!/usr/bin/env bash
# bin/state-init — write initial state.json from JSON stdin.
# Stdin: {"scope":..., "scope_slug":..., "axes":{...}, "target_metric":...}
# Usage: state-init --slug <slug>
set -euo pipefail

slug=""
while [[ $# -gt 0 ]]; do
  case "$1" in --slug) slug="$2"; shift 2 ;; *) echo "unknown arg" >&2; exit 2 ;; esac
done
[[ -z "$slug" ]] && { echo "--slug required" >&2; exit 2; }

home="${GSTACK_HOME:-$HOME/.gstack}"
dir="$home/projects/$slug/autoresearch"
mkdir -p "$dir"

now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
session_id="ar-$(date -u +%Y-%m-%d-%H%M%S)"

input=$(cat)

jq -n --argjson input "$input" --arg now "$now" --arg sid "$session_id" '{
  schema_version: 1,
  session_id: $sid,
  session_started_at: $now,
  last_iteration_at: $now,
  phase: "planning",
  scope: $input.scope,
  scope_slug: $input.scope_slug,
  target_metric: $input.target_metric,
  axes: $input.axes,
  candidate_queue: [],
  results_history: [],
  current_best: null,
  pivot_history: [],
  research_log: {available: false, session_path: null, fallback_path: null},
  iteration_count: 0,
  stop_reason: null
}' > "$dir/state.json"

echo "$dir/state.json"
```

- [ ] **Step 4: Implement state-read**

```bash
#!/usr/bin/env bash
# bin/state-read — read field from state.json via jq path.
# Usage: state-read --slug <slug> --path <jq-path>
set -euo pipefail
slug=""; path=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) slug="$2"; shift 2 ;;
    --path) path="$2"; shift 2 ;;
    *) echo "unknown arg" >&2; exit 2 ;;
  esac
done
[[ -z "$slug" || -z "$path" ]] && { echo "--slug and --path required" >&2; exit 2; }
home="${GSTACK_HOME:-$HOME/.gstack}"
jq -r "$path" "$home/projects/$slug/autoresearch/state.json"
```

- [ ] **Step 5: Implement state-update**

```bash
#!/usr/bin/env bash
# bin/state-update — apply a jq filter to state.json (in-place).
# Usage: state-update --slug <slug> --set '<jq-filter>'
# Example: state-update --slug X --set '.phase = "running"'
set -euo pipefail
slug=""; filter=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --slug) slug="$2"; shift 2 ;;
    --set) filter="$2"; shift 2 ;;
    *) echo "unknown arg" >&2; exit 2 ;;
  esac
done
[[ -z "$slug" || -z "$filter" ]] && { echo "--slug and --set required" >&2; exit 2; }

home="${GSTACK_HOME:-$HOME/.gstack}"
file="$home/projects/$slug/autoresearch/state.json"
tmp=$(mktemp)
now=$(date -u +%Y-%m-%dT%H:%M:%SZ)
# Always update last_iteration_at on every change
jq --arg now "$now" "($filter) | .last_iteration_at = \$now" "$file" > "$tmp"
mv "$tmp" "$file"
```

- [ ] **Step 6: Implement state-validate**

```bash
#!/usr/bin/env bash
# bin/state-validate — exit 0 if state.json is valid, 1 otherwise.
# Validates: parseable JSON, schema_version=1, required fields present.
set -euo pipefail
slug=""
while [[ $# -gt 0 ]]; do
  case "$1" in --slug) slug="$2"; shift 2 ;; *) exit 2 ;; esac
done
[[ -z "$slug" ]] && exit 2
home="${GSTACK_HOME:-$HOME/.gstack}"
file="$home/projects/$slug/autoresearch/state.json"
[[ -f "$file" ]] || exit 1
jq -e 'has("schema_version") and .schema_version==1 and has("phase") and has("scope_slug") and has("axes") and has("candidate_queue") and has("results_history")' "$file" >/dev/null 2>&1 || exit 1
exit 0
```

- [ ] **Step 7: chmod + tests pass**

```bash
chmod +x skills/autoresearch/bin/state-{init,read,update,validate}
bats skills/autoresearch/tests/state-roundtrip.bats
```

Expected: 4 tests pass.

- [ ] **Step 8: Commit**

```bash
git add skills/autoresearch/bin/state-* skills/autoresearch/tests/state-roundtrip.bats
git commit -m "feat(autoresearch): state.json helpers (init/read/update/validate) + tests"
```

---

### Task 6: Implement bin/research-log-detect + tests

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/research-log-detect`
- Create: `~/arcadia/superstack/skills/autoresearch/tests/research-log-detect.bats`

- [ ] **Step 1: Write the failing tests**

```bash
# tests/research-log-detect.bats
load helpers

@test "research-log-detect exits 0 when ~/arcadia/research-log/ exists with .git" {
  fake_log="$TEST_DIR/research-log"
  mkdir -p "$fake_log/.git"
  RESEARCH_LOG_ROOT="$fake_log" run "$AUTORESEARCH_BIN/research-log-detect"
  [ "$status" -eq 0 ]
}

@test "research-log-detect exits 1 when dir absent" {
  RESEARCH_LOG_ROOT="$TEST_DIR/nope" run "$AUTORESEARCH_BIN/research-log-detect"
  [ "$status" -eq 1 ]
}

@test "research-log-detect exits 1 when dir present but not a git repo" {
  fake_log="$TEST_DIR/research-log"
  mkdir -p "$fake_log"
  RESEARCH_LOG_ROOT="$fake_log" run "$AUTORESEARCH_BIN/research-log-detect"
  [ "$status" -eq 1 ]
}
```

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Implement**

```bash
#!/usr/bin/env bash
# bin/research-log-detect — exit 0 if research-log is set up and pushable, 1 otherwise.
set -euo pipefail
root="${RESEARCH_LOG_ROOT:-$HOME/arcadia/research-log}"
[[ -d "$root/.git" ]] && exit 0 || exit 1
```

- [ ] **Step 4: chmod + run tests**

```bash
chmod +x skills/autoresearch/bin/research-log-detect
bats skills/autoresearch/tests/research-log-detect.bats
```

Expected: 3 tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/autoresearch/bin/research-log-detect skills/autoresearch/tests/research-log-detect.bats
git commit -m "feat(autoresearch): research-log-detect helper + tests"
```

---

### Task 7: Implement research-log-init-entry + research-log-append + notes-append-local

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/research-log-init-entry`
- Create: `~/arcadia/superstack/skills/autoresearch/bin/research-log-append`
- Create: `~/arcadia/superstack/skills/autoresearch/bin/notes-append-local`

These are write-helpers that integrate with the user's existing research-log format. Keep them minimal — the LLM produces the markdown content; these helpers handle file/git mechanics.

- [ ] **Step 1: Implement research-log-init-entry**

```bash
#!/usr/bin/env bash
# bin/research-log-init-entry — create a new YYYY-MM-DD_autoresearch-<slug>.md
# Usage: research-log-init-entry --top-level <brainlab|wolong|...> --project <slug> --scope-slug <slug>
# Stdin: full markdown body of the initial entry
# Stdout: absolute path to the created file
set -euo pipefail
top_level=""; project=""; scope_slug=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --top-level) top_level="$2"; shift 2 ;;
    --project) project="$2"; shift 2 ;;
    --scope-slug) scope_slug="$2"; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ -z "$top_level" || -z "$project" || -z "$scope_slug" ]] && exit 2

root="${RESEARCH_LOG_ROOT:-$HOME/arcadia/research-log}"
date=$(date +%Y-%m-%d)
dir="$root/$top_level/$project"
mkdir -p "$dir"
file="$dir/${date}_autoresearch-${scope_slug}.md"
cat > "$file"  # body from stdin

(
  cd "$root"
  git pull --rebase origin main >/dev/null 2>&1 || true
  git add "$file"
  git commit -m "autoresearch: init session entry $top_level/$project/$(basename "$file")" >/dev/null
  git push origin main >/dev/null 2>&1 || echo "push deferred (offline?)" >&2
)
echo "$file"
```

- [ ] **Step 2: Implement research-log-append**

```bash
#!/usr/bin/env bash
# bin/research-log-append — append a block to an existing entry, then commit + push.
# Usage: research-log-append --file <path> --commit-message <msg>
# Stdin: markdown block to append (will be prefixed with two newlines)
set -euo pipefail
file=""; msg=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --file) file="$2"; shift 2 ;;
    --commit-message) msg="$2"; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ -z "$file" || -z "$msg" ]] && exit 2

block=$(cat)
{ printf "\n\n"; printf "%s\n" "$block"; } >> "$file"

root="${RESEARCH_LOG_ROOT:-$HOME/arcadia/research-log}"
(
  cd "$root"
  git pull --rebase origin main >/dev/null 2>&1 || true
  git add "$file"
  git commit -m "$msg" >/dev/null
  git push origin main >/dev/null 2>&1 || echo "push deferred (offline?)" >&2
)
```

- [ ] **Step 3: Implement notes-append-local**

```bash
#!/usr/bin/env bash
# bin/notes-append-local — append to ~/.gstack/projects/<slug>/autoresearch/notes.md.
# Usage: notes-append-local --slug <slug>
# Stdin: markdown block to append
set -euo pipefail
slug=""
while [[ $# -gt 0 ]]; do case "$1" in --slug) slug="$2"; shift 2 ;; *) exit 2 ;; esac; done
[[ -z "$slug" ]] && exit 2

home="${GSTACK_HOME:-$HOME/.gstack}"
dir="$home/projects/$slug/autoresearch"
mkdir -p "$dir"
file="$dir/notes.md"
[[ -f "$file" ]] || printf "# autoresearch notes for %s\n" "$slug" > "$file"
{ printf "\n\n"; cat; } >> "$file"
echo "$file"
```

- [ ] **Step 4: chmod**

```bash
chmod +x skills/autoresearch/bin/research-log-init-entry
chmod +x skills/autoresearch/bin/research-log-append
chmod +x skills/autoresearch/bin/notes-append-local
```

- [ ] **Step 5: Smoke test**

```bash
# Local notes path (no research-log dependency)
GSTACK_HOME=/tmp/test-gstack-1 \
  bash -c 'echo "hello" | skills/autoresearch/bin/notes-append-local --slug demo' \
  && cat /tmp/test-gstack-1/projects/demo/autoresearch/notes.md
```

Expected: `# autoresearch notes for demo` followed by `hello`.

- [ ] **Step 6: Commit**

```bash
git add skills/autoresearch/bin/research-log-init-entry skills/autoresearch/bin/research-log-append skills/autoresearch/bin/notes-append-local
git commit -m "feat(autoresearch): research-log + local notes append helpers"
```

---

### Task 8: Implement bin/commit-experiment + tests

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/commit-experiment`
- Create: `~/arcadia/superstack/skills/autoresearch/tests/commit-experiment.bats`

- [ ] **Step 1: Write the failing test**

```bash
# tests/commit-experiment.bats
load helpers

@test "commit-experiment commits with autoresearch-prefixed message" {
  cd "$FAKE_PROJECT"
  echo "data" > experiment.txt
  run "$AUTORESEARCH_BIN/commit-experiment" --scope-slug test --iter 1 --candidate c001
  [ "$status" -eq 0 ]
  log=$(git -C "$FAKE_PROJECT" log -1 --pretty=%s)
  [[ "$log" == *"autoresearch"* ]]
  [[ "$log" == *"c001"* ]]
}

@test "commit-experiment exits 0 with no-op message when nothing to stage" {
  cd "$FAKE_PROJECT"
  run "$AUTORESEARCH_BIN/commit-experiment" --scope-slug test --iter 1 --candidate c001
  [ "$status" -eq 0 ]
}
```

- [ ] **Step 2: Run to verify fail**

- [ ] **Step 3: Implement**

```bash
#!/usr/bin/env bash
# bin/commit-experiment — stage everything in the project repo and commit with
# a structured autoresearch message. No-op (exit 0) if there's nothing to commit.
# Usage: commit-experiment --scope-slug <slug> --iter <N> --candidate <cid> [--message-suffix <text>]
set -euo pipefail
scope=""; iter=""; cand=""; suffix=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --scope-slug) scope="$2"; shift 2 ;;
    --iter) iter="$2"; shift 2 ;;
    --candidate) cand="$2"; shift 2 ;;
    --message-suffix) suffix="$2"; shift 2 ;;
    *) exit 2 ;;
  esac
done
[[ -z "$scope" || -z "$iter" || -z "$cand" ]] && exit 2

git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repo" >&2; exit 1; }

# Stage everything tracked + untracked under cwd
git add -A

# Bail clean if nothing to commit
if git diff --cached --quiet; then
  echo "no-op (nothing staged)"
  exit 0
fi

msg="autoresearch($scope) iter=$iter cand=$cand"
[[ -n "$suffix" ]] && msg="$msg — $suffix"
git commit -m "$msg"
```

- [ ] **Step 4: chmod + tests pass**

```bash
chmod +x skills/autoresearch/bin/commit-experiment
bats skills/autoresearch/tests/commit-experiment.bats
```

Expected: 2 tests pass.

- [ ] **Step 5: Commit**

```bash
git add skills/autoresearch/bin/commit-experiment skills/autoresearch/tests/commit-experiment.bats
git commit -m "feat(autoresearch): commit-experiment helper + tests"
```

---

### Task 9: Implement bin/stash-and-fix-prep (code-fix safety boundary)

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/bin/stash-and-fix-prep`

This is a thin wrapper that the SKILL.md calls before attempting an agentic code-fix. Records the stash ref so the LLM can pop it cleanly if the fix fails.

- [ ] **Step 1: Implement**

```bash
#!/usr/bin/env bash
# bin/stash-and-fix-prep — stash the working tree, output the stash ref to stdout.
# Used before an agentic code-fix attempt. If the fix makes things worse,
# the SKILL.md calls `git stash pop <ref>` to revert.
# If the working tree is clean, output empty stdout (caller treats as no-op).
set -euo pipefail
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { echo "not a git repo" >&2; exit 1; }
if git diff --quiet && git diff --cached --quiet && [[ -z "$(git ls-files --others --exclude-standard)" ]]; then
  # nothing to stash
  exit 0
fi
out=$(git stash push --include-untracked --message "autoresearch:code-fix-prep" 2>&1)
ref=$(git stash list --pretty='%gd' | head -1)
echo "$ref"
```

- [ ] **Step 2: chmod + smoke test**

```bash
chmod +x skills/autoresearch/bin/stash-and-fix-prep
cd /tmp && rm -rf demo-stash && mkdir demo-stash && cd demo-stash
git init -q && git commit -q --allow-empty -m init
echo "x" > foo.txt
~/arcadia/superstack/skills/autoresearch/bin/stash-and-fix-prep
# expect: stash@{0}
git stash list
```

- [ ] **Step 3: Commit**

```bash
cd ~/arcadia/superstack
git add skills/autoresearch/bin/stash-and-fix-prep
git commit -m "feat(autoresearch): stash-and-fix-prep helper for code-fix safety boundary"
```

---

### Task 10: Write prompts/axis-enumeration.md

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/prompts/axis-enumeration.md`

- [ ] **Step 1: Write the prompt**

```markdown
# Axis enumeration prompt

You are bootstrapping an /autoresearch session. The user gave you a free-text scope describing what to explore. Convert it into a concrete experiment search space.

**Inputs:**
- `scope`: free-text description (e.g. "iterate over architectures, input modes, loss functions for the FW prediction model")
- `project_context`: a Read of the user's project README/CLAUDE.md/relevant code if useful

**Outputs (JSON, no prose):**

```json
{
  "scope_slug": "<2-3 hyphenated words capturing the search domain>",
  "target_metric": {"name": "<metric>", "op": ">|<|>=|<=|=", "threshold": <number>} or null if user did not specify,
  "axes": {
    "<category1>": ["<value1>", "<value2>", ...],
    "<category2>": ["<value1>", ...]
  },
  "rationale": "<1-2 sentences on why these axes were chosen>"
}
```

**Rules:**
1. Each axis is a category with 2-8 concrete options. Don't enumerate continuous ranges as discrete values unless the user named them.
2. Stick close to what the scope says. Don't invent unrelated dimensions.
3. If the user named a target metric in the scope ("until val_corr > 0.85"), parse it. If not, set target_metric to null and rely on exhaustion-stop.
4. scope_slug is filename-safe (lowercase, hyphens, no special chars). Should make sense as a research-log entry slug.
5. If you can't make sense of the scope, return `{"error": "<one-sentence reason>"}` instead — the SKILL.md handles the error path.

**Cardinality budget:**
The full Cartesian product of axes is the worst-case search space. Keep it under ~50 cells unless the scope explicitly asks for exhaustive sweep. If the product would exceed 50, propose smaller axis vocabularies.
```

- [ ] **Step 2: Commit**

```bash
git add skills/autoresearch/prompts/axis-enumeration.md
git commit -m "feat(autoresearch): axis-enumeration prompt"
```

---

### Task 11: Write prompts/adaptive-replan.md

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/prompts/adaptive-replan.md`

- [ ] **Step 1: Write the prompt**

```markdown
# Adaptive replan prompt

You are mid-run in an /autoresearch session. After each iteration, you decide what to try next based on what you've learned so far.

**Inputs:**
- `state.json`: full current state (axes, candidate_queue, results_history, current_best, pivot_history)
- Just-completed iteration's result (or failure)

**Output (JSON, no prose):**

```json
{
  "next_candidate": {
    "id": "c<NNN>",
    "axes": {"arch": "...", "input": "...", ...},
    "priority": <float, higher = more promising>
  } or null if queue should drain naturally,
  "queue_updates": {
    "add": [<new candidates to enqueue>],
    "remove": [<candidate ids to drop from queue>],
    "reprioritize": [{"id": "c<NNN>", "priority": <float>}]
  },
  "pivot": {
    "happened": true|false,
    "from_category": "<axis name>" or null,
    "to_category": "<axis name>" or null,
    "reason": "<one sentence>" or null
  },
  "log_block": "<3-5 line markdown block to append to the research-log entry. Plain prose, no headers.>",
  "promote_to_result_block": "<full markdown ## RESULT block if this iteration was meaningful, else empty string>",
  "rationale": "<2-3 sentences on the strategy update>"
}
```

**Rules:**
1. Adaptive replanning is the whole point. Do NOT just dequeue the next candidate from `candidate_queue` mechanically — actually think about what the results so far suggest. New candidates can deviate from the original axes if results push you to a new hypothesis.
2. **Pivot detection**: a pivot is when next_candidate's primary axis differs from current axis being explored. Set `pivot.happened: true` and write a one-sentence reason. The SKILL.md uses this to add a `## PIVOT` header to the log file.
3. **Meaningful result detection**: a result is meaningful if (a) it's notably better than current_best by >5% on the target metric, (b) it falsifies a hypothesis (whole branch underperforms), or (c) it surprises you. Write the markdown ## RESULT block when meaningful, else empty string.
4. The candidate queue is a hint, not a contract. You can rewrite it.
5. Cap log_block at 5 lines. Be concrete: "Tried unet+t1+mse → val_corr=0.72 (best so far); next: transformer+t1+mse to test arch effect at fixed input/loss."
6. If you have no idea what to try next AND the queue is empty AND nothing in results_history suggests a new axis, output `{"next_candidate": null, ..., "rationale": "search space exhausted"}` — this triggers the exhaustion stop.
```

- [ ] **Step 2: Commit**

```bash
git add skills/autoresearch/prompts/adaptive-replan.md
git commit -m "feat(autoresearch): adaptive-replan prompt"
```

---

### Task 12: Write prompts/error-classification.md and prompts/code-fix.md

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/prompts/error-classification.md`
- Create: `~/arcadia/superstack/skills/autoresearch/prompts/code-fix.md`

- [ ] **Step 1: Write error-classification.md**

```markdown
# Error classification prompt

You're inside /autoresearch and an experiment iteration just failed. Classify the error so the SKILL.md knows whether to retry, attempt a code-fix, or halt.

**Inputs:**
- `last_iteration.log`: full stdout/stderr from the failed run
- The candidate that was being run (axes)
- Recent error history (count of consecutive failures across recent candidates)

**Output (JSON, no prose):**

```json
{
  "class": "transient|code_bug|infrastructure|unknown",
  "evidence": "<1-2 sentences quoting the part of the log that drove the classification>",
  "suggested_action": "retry|code_fix|halt|skip",
  "retry_adjustment": "<1 sentence describing the adjustment if class=transient — e.g. 'reduce batch size to 8' — else null>",
  "fix_target": "<file:line if class=code_bug, else null>"
}
```

**Classification rules (be liberal toward fight-through):**

- **transient**: CUDA OOM, "Bus error", file lock, transient network failure during data download, intermittent SSH/NFS hiccup, "device-side assert" that's likely flake. Action: retry (up to 3 times in SKILL.md outer loop). Suggest a retry adjustment if obvious.
- **code_bug**: Python traceback whose deepest frame is in user code, AttributeError/NameError/TypeError on user code, ImportError of a project module, IndexError on a tensor reshape. Action: code_fix.
- **infrastructure**: "No space left on device", "CUDA driver version is insufficient", "GPU not found" persisting across retries, "Permission denied" on filesystem write to project, conda env missing. Action: halt.
- **unknown**: when the log doesn't fit any of the above. Action: skip (mark candidate dead, continue with next). Bias toward `unknown→skip` over `unknown→halt` so the loop keeps going.

**Bias rule:** When in doubt between transient and code_bug, choose code_bug — it's better to attempt a fix than to retry a deterministic failure.

When in doubt between code_bug and unknown, choose code_bug if you can identify a specific file:line; else unknown.

When in doubt between infrastructure and anything else, do NOT choose infrastructure unless the evidence is unambiguous. Halting is the worst outcome for the user (they're not present to resolve it). Strongly prefer skip-and-continue.
```

- [ ] **Step 2: Write code-fix.md**

```markdown
# Code-fix proposal prompt

You're inside /autoresearch. The error-classification prompt determined that the last failure was a code_bug. Propose a small Edit to fix it.

**Inputs:**
- `last_iteration.log`: full traceback
- `fix_target`: file:line from the classification
- The actual file content around fix_target (read it before proposing)
- Previous fix attempts on this candidate (max 3 total)

**Output (JSON, no prose):**

```json
{
  "fix_kind": "edit|noop",
  "explanation": "<1 sentence: what's wrong and what your fix does>",
  "edit": {
    "file": "<absolute path>",
    "old_string": "<exact substring to replace, must be unique in file>",
    "new_string": "<replacement>"
  } or null if fix_kind=noop,
  "confidence": <float 0-1>,
  "expected_outcome": "<1 sentence: what should happen on rerun>"
}
```

**Rules:**
1. Stay surgical. Fix the smallest possible thing. Do NOT refactor.
2. The fix must target the specific traceback line. Don't fix unrelated code "while you're there."
3. Common fix patterns:
   - Argument order/name mismatch on a function call
   - Missing import
   - Wrong attribute name on a tensor or module
   - Off-by-one on a slice or reshape
   - dtype/device mismatch (add `.to(device)` or `.float()`)
4. If you've already attempted 2 fixes on this candidate and neither worked, output `{"fix_kind": "noop", "explanation": "two fix attempts failed; marking candidate dead", ...}`.
5. NEVER edit:
   - Configuration files outside the project's source dir
   - Anything under `.git/`, `.gstack/`, `~/.claude/`
   - Files the traceback doesn't directly point at — your fix must be in the file from fix_target.
6. **Working tree safety:** SKILL.md will `git stash` before applying your edit and restore the stash if rerun fails harder. You don't need to worry about cleanup; just propose a clean Edit.
```

- [ ] **Step 3: Commit**

```bash
git add skills/autoresearch/prompts/error-classification.md skills/autoresearch/prompts/code-fix.md
git commit -m "feat(autoresearch): error-classification and code-fix prompts"
```

---

### Task 13: Write SKILL.md — frontmatter + INIT mode (plan-confirm at launch)

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/SKILL.md` (this task: frontmatter + INIT mode only; RUNNING mode is added in Task 14)

This is the largest task — splitting between INIT and RUNNING modes for reviewability.

- [ ] **Step 1: Write frontmatter + intro + INIT-mode body**

```markdown
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

if [[ -f "$state_file" ]] && "$SKILL_DIR/bin/state-validate" --slug "$slug"; then
  MODE="running"
  PHASE=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .phase)
  ITER=$("$SKILL_DIR/bin/state-read" --slug "$slug" --path .iteration_count)
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
```

- [ ] **Step 2: Sanity-check the markdown**

Render to make sure the code blocks aren't mangled, frontmatter parses, etc.

```bash
head -3 skills/autoresearch/SKILL.md  # frontmatter present
grep -c '^```' skills/autoresearch/SKILL.md  # should be even
```

- [ ] **Step 3: Commit**

```bash
git add skills/autoresearch/SKILL.md
git commit -m "feat(autoresearch): SKILL.md frontmatter + INIT mode body"
```

---

### Task 14: Append SKILL.md — RUNNING mode (iteration loop)

**Files:**
- Modify: `~/arcadia/superstack/skills/autoresearch/SKILL.md` (append RUNNING mode + termination handling)

- [ ] **Step 1: Append RUNNING mode body**

```markdown
## RUNNING mode

Triggered when state.json exists and phase=running. This is the workhorse iteration body. Everything below is non-blocking — no AskUserQuestion calls, no human in the loop.

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
   - `class=transient`: retry the same candidate up to 3 times total with the suggested adjustment. If still failing, treat as code_bug.
   - `class=code_bug`: stash, attempt code-fix, rerun. Up to 3 fix attempts.
     - Each attempt: `STASH_REF=$($SKILL_DIR/bin/stash-and-fix-prep)` → apply LLM-proposed Edit → rerun.
     - On rerun success: keep the fix (don't pop the stash; the user keeps the fix in working tree). Commit via `commit-experiment`.
     - On rerun failure: `git stash pop "$STASH_REF"` to revert the failed fix. Try a different fix. After 3 attempts, mark candidate dead.
   - `class=infrastructure`: write final summary with `## INFRASTRUCTURE FAILURE` block, set phase=halted, do NOT call ScheduleWakeup. Exit.
   - `class=unknown`: log + skip + continue.

### Step 5 — Update state with result

On success or recovery:

```bash
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
    notes: \"\"
  }]
"

# Update current_best if applicable (per target_metric.op direction)
```

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

"$SKILL_DIR/bin/state-update" --slug "$slug" \
  --set ".phase = \"$PHASE_FINAL\" | .stop_reason = \"$STOP_REASON\""

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
```

- [ ] **Step 2: Verify SKILL.md is well-formed**

```bash
wc -l skills/autoresearch/SKILL.md
grep -c '^## ' skills/autoresearch/SKILL.md  # section count
```

Expected: substantial line count (~500+), at least 8 H2 sections (Modes, Pre-flight, INIT mode, RUNNING mode, Termination, Question deferral mailbox, etc.).

- [ ] **Step 3: Commit**

```bash
git add skills/autoresearch/SKILL.md
git commit -m "feat(autoresearch): SKILL.md RUNNING mode + termination + mailbox"
```

---

### Task 15: Write README.md and USAGE.md

**Files:**
- Create: `~/arcadia/superstack/skills/autoresearch/README.md`
- Create: `~/arcadia/superstack/skills/autoresearch/USAGE.md`

- [ ] **Step 1: Write README.md**

```markdown
# /autoresearch

Long-running autonomous research loops for Claude Code. Invoke once, walk away for hours or days. Adaptive replanning each iteration, agentic code-fix on failures, optional research-log push, STOP-file kill switch.

## Quick start

```
/autoresearch "iterate over architectures, input modes, and loss functions for the FW prediction model. target: val_corr > 0.85"
```

You'll be asked once to confirm the planned axes, then the loop runs without further prompts.

## Files

- `DESIGN.md` — full design doc + rationale (read this if anything is unclear)
- `IMPLEMENTATION_PLAN.md` — task-by-task build plan (already executed if you're reading this)
- `USAGE.md` — invocation examples + state.json layout + how to halt cleanly
- `SKILL.md` — the skill itself (loaded by Claude Code)
- `bin/` — bash helpers
- `prompts/` — prompt fragments loaded by SKILL.md
- `tests/` — bats tests for the bash helpers

## Status

Built 2026-04-30. v0 — calibration may be needed for prompt tuning on first real run.
```

- [ ] **Step 2: Write USAGE.md**

```markdown
# /autoresearch USAGE

## Invoke

```
/autoresearch "<free-text scope>"
```

The scope text should describe what to explore and (optionally) when to stop. Examples:

- `/autoresearch "iterate over architectures, input modes, loss functions for the FW model. target: val_corr > 0.85"`
- `/autoresearch "sweep learning rate × batch size × optimizer for the small classifier"`
- `/autoresearch "try data augmentations and dropout values to reduce overfitting on val_loss"`

You'll be asked ONCE at launch to confirm the planned axes. Choose:

- **Confirm and launch** — start the loop
- **Edit axes** — redirect via free-text
- **Cancel** — exit without writing state

After launch, the loop self-paces and runs without prompts.

## Halt

```bash
touch ~/.gstack/projects/<slug>/autoresearch/STOP
```

The skill checks for this file at the start of each iteration. It finishes the in-flight iteration cleanly, writes a final summary, and exits.

## Resume after a Claude Code crash

State is persisted at `~/.gstack/projects/<slug>/autoresearch/state.json`. To resume:

```
/autoresearch
```

(no args) — picks up from existing state.json.

## Inspect

- State: `~/.gstack/projects/<slug>/autoresearch/state.json`
- Last iteration log: `~/.gstack/projects/<slug>/autoresearch/last-iteration.log`
- Deferred questions: `~/.gstack/projects/<slug>/autoresearch/QUESTIONS_FOR_USER.md`
- Live narrative: research-log entry (if set up) or local `notes.md`

## state.json schema (v1)

See `DESIGN.md` for full schema. Phase transitions: `planning → running → (completed | halted | cancelled)`.

## Modes

- **INIT** — first invocation, no state.json. Plans axes, asks for confirmation, schedules iter 1.
- **RUNNING** — every subsequent invocation (fired by ScheduleWakeup). Runs one iteration, replans, schedules next.

## When research-log isn't set up

If `~/arcadia/research-log/` is absent or not a git repo, the skill falls back to a local `~/.gstack/projects/<slug>/autoresearch/notes.md`. Setup-agnostic.
```

- [ ] **Step 3: Commit**

```bash
git add skills/autoresearch/README.md skills/autoresearch/USAGE.md
git commit -m "docs(autoresearch): README.md and USAGE.md"
```

---

### Task 16: Run all bats tests + smoke-test the skeleton

**Files:** none (verification only)

- [ ] **Step 1: Run all bats tests**

```bash
cd ~/arcadia/superstack/skills/autoresearch
bats tests/
```

Expected: all tests pass. If anything fails, debug and fix before continuing.

- [ ] **Step 2: Smoke-test the skill registration**

```bash
ls ~/arcadia/superstack/skills/autoresearch/SKILL.md
head -3 ~/arcadia/superstack/skills/autoresearch/SKILL.md  # frontmatter
```

Expected: file exists; frontmatter has `name: autoresearch`.

- [ ] **Step 3: Verify skill discovery**

The skill should be invokable as `/autoresearch` once superstack is on the skill path. The setup script handles this; verify it picked up the new dir.

```bash
cd ~/arcadia/superstack && ./setup
# Expected: setup re-runs idempotently, no errors, autoresearch is now linked into the Claude Code skill path
```

- [ ] **Step 4: No commit (verification step only)**

---

### Task 17: Calibration run on a toy project

**Files:** none (operational test)

This is the first end-to-end test. Pick a small project (or a scratch dir) where you can afford a few wasted iterations. The goal is to surface bugs in the prompts and iteration logic before the skill is used on real research.

- [ ] **Step 1: Set up a toy project**

```bash
mkdir -p /tmp/autoresearch-toy && cd /tmp/autoresearch-toy
git init -q && git commit -q --allow-empty -m init
cat > train.py <<'EOF'
import argparse, random, json
ap = argparse.ArgumentParser()
ap.add_argument("--arch")
ap.add_argument("--lr", type=float)
args = ap.parse_args()
# Fake training: arch & lr both matter; "best" is mlp + lr=0.01
score = 0.5 + (0.2 if args.arch == "mlp" else 0.0) + (0.15 if args.lr == 0.01 else 0.0) + random.uniform(-0.02, 0.02)
print(json.dumps({"val_corr": round(score, 3)}))
EOF
cat > CLAUDE.md <<'EOF'
# Toy autoresearch project

Train via `python train.py --arch <unet|transformer|mlp> --lr <0.001|0.01|0.1>`. Stdout is a JSON with `val_corr`.
EOF
git add -A && git commit -q -m "toy project for autoresearch calibration"
```

- [ ] **Step 2: Invoke /autoresearch**

In a Claude Code session at `/tmp/autoresearch-toy`:

```
/autoresearch "sweep arch and lr to maximize val_corr. target: val_corr > 0.80"
```

- [ ] **Step 3: Confirm at the launch gate**

Watch the planned axes. Confirm. Walk away for ~5 minutes.

- [ ] **Step 4: Inspect outcomes**

```bash
ls ~/.gstack/projects/autoresearch-toy/autoresearch/
cat ~/.gstack/projects/autoresearch-toy/autoresearch/state.json | jq .iteration_count
cat ~/.gstack/projects/autoresearch-toy/autoresearch/state.json | jq .current_best
git -C /tmp/autoresearch-toy log --oneline
```

Expected: state.json shows several iterations, current_best converges on `arch=mlp, lr=0.01`, project repo has commits per iteration. If `~/arcadia/research-log/` is set up, a session entry exists there too.

- [ ] **Step 5: Test the STOP file**

```bash
touch ~/.gstack/projects/autoresearch-toy/autoresearch/STOP
# Wait one iteration cycle (~1-2 min)
cat ~/.gstack/projects/autoresearch-toy/autoresearch/state.json | jq .phase
```

Expected: phase=cancelled, final summary appended to log.

- [ ] **Step 6: Document calibration findings**

If anything was off (prompts didn't enumerate axes well, replan didn't pivot when it should have, error classification mis-bucketed), open a follow-up note. Each finding becomes a tweak to a prompt file or a SKILL.md section.

- [ ] **Step 7: Commit any prompt fixes**

```bash
git add skills/autoresearch/prompts/
git commit -m "tune(autoresearch): prompt tweaks from calibration run"
```

---

### Task 18: Self-review pass + final commit

**Files:** none (review only)

- [ ] **Step 1: Spec coverage check**

For each section in `DESIGN.md`, confirm a task implements it:

- D1 search-space spec → Tasks 10, 13 (axis-enumeration prompt + INIT mode plan-confirm)
- D2 research-log cadence → Tasks 7, 14 (research-log helpers + RUNNING mode append logic)
- D3 stop conditions → Tasks 4, 14 (stop-check helper + RUNNING mode Step 1)
- D4 failure handling → Tasks 9, 12, 14 (stash-prep, error/code-fix prompts, RUNNING mode Step 4)
- D5 state location → Tasks 5 (all state-* helpers under ~/.gstack/projects/<slug>/autoresearch/)
- D6 mailbox → Task 14 (Question deferral mailbox section)
- D7 scope-slug parsing → Task 10 (axis-enumeration produces it)

- [ ] **Step 2: Placeholder scan**

Search for "TODO", "TBD", "<...>", "implement later" in the skill files (not code blocks that intentionally show placeholders for the LLM to fill in):

```bash
cd ~/arcadia/superstack/skills/autoresearch
grep -n 'TODO\|TBD\|implement later' SKILL.md README.md USAGE.md prompts/*.md bin/* tests/*.bats || echo "clean"
```

- [ ] **Step 3: Type/name consistency**

Spot-check:
- `state-init`/`state-read`/`state-update`/`state-validate` all use the same `--slug` arg?
- `state.json` field names consistent across helpers + SKILL.md examples?
- Phase enum values match between schema and SKILL.md transitions?

- [ ] **Step 4: Final commit if anything was fixed**

```bash
git status
git add -A && git commit -m "fix(autoresearch): self-review consistency tweaks" || echo "nothing to fix"
```

---

## Next-session handoff prompt

Copy-paste this into a fresh Claude Code session to continue the pipeline. The fresh session does NOT need any context from the design conversation — DESIGN.md and IMPLEMENTATION_PLAN.md are self-contained.

```
Continue /pipeline at Step 3 (/plan-eng-review) for /autoresearch.

Project: ~/arcadia/superstack (jinchiwei/superstack on GitHub).
Branch: main.

Design doc: ~/arcadia/superstack/skills/autoresearch/DESIGN.md (Status: APPROVED, Approach B chosen).
Implementation plan: ~/arcadia/superstack/skills/autoresearch/IMPLEMENTATION_PLAN.md (18 tasks, ~600-1000 lines of skill prose + bash helpers + bats tests).

Read both, then run /plan-eng-review on the implementation plan. Focus areas:
- Agentic code-fix git-stash safety (Task 9 + Task 14 Step 4)
- ScheduleWakeup pacing under rate limits (Task 14 Step 9)
- state.json schema versioning (Task 5 + the schema_version=1 in DESIGN.md)
- error-classification bias (Task 12 — the "fight HARD through the mess" requirement means the classifier should NEVER halt on infrastructure unless evidence is unambiguous)

After /plan-eng-review, proceed to:
4. /guard ~/arcadia/superstack/skills/autoresearch
5. /subagent-driven-development on the implementation plan
6. /review
7. /codex review
8. /ship (superstack PR)

The user wants the autoresearch implementation done in this fresh session — they handed off here specifically to keep context clean for the build. Don't ask why.
```

---

## Self-review (skill-mandated)

**Spec coverage:** All seven design areas (D1-D7) plus premises P1-P5 are covered by Tasks 1-18. ✓

**Placeholders:** None remain. The `<...>` markers in SKILL.md prose are intentional (instructions to the LLM at runtime to substitute values from state.json), not unfilled plan TODOs.

**Type consistency:** All bash helpers use `--slug <slug>` consistently. `state.json` schema is defined once and referenced by helpers + SKILL.md. Phase values (`planning|running|halted|completed|cancelled`) are consistent across DESIGN.md, schema definition, and termination code in Task 14.

---

## Execution choice

**Recommended: hand off to a fresh Claude Code session for /subagent-driven-development.** The current session has heavy AGF context, /pipeline meta-conversation, and prior compacted history. Build phase wants a clean context budget. Use the next-session handoff prompt above.
