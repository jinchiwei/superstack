load helpers

# These tests verify the D4 LOCKED consecutive-infra-count gate. The SKILL.md
# RUNNING-mode failure pipeline performs the same state-update sequence; this
# is the regression contract for that math.

setup_state() {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project >/dev/null
}

# Apply the D4 gate. Returns 0 if HALT condition reached, 1 if continue.
record_infra() {
  cand_id="$1"
  candidates=$("$AUTORESEARCH_BIN/state-read" --slug test-project --path '.consecutive_infra_candidates')
  if echo "$candidates" | jq -e --arg id "$cand_id" 'index($id)' >/dev/null; then
    return 1   # already counted — treat as skip, no halt
  fi
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set "
    .consecutive_infra_count += 1
    | .consecutive_infra_candidates += [\"$cand_id\"]
  "
  count=$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)
  [[ "$count" -ge 2 ]] && return 0 || return 1
}

# Reset on any non-infra outcome.
reset_infra() {
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set '
    .consecutive_infra_count = 0
    | .consecutive_infra_candidates = []
  '
}

@test "single infra classification — no halt, count=1" {
  setup_state
  run record_infra "c001"
  [ "$status" -eq 1 ]   # 1 = continue
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)" = "1" ]
}

@test "same candidate twice — count stays at 1 (dedupe)" {
  setup_state
  record_infra "c001" || true
  run record_infra "c001"
  # Same cand → already counted, still continue (dedupe)
  [ "$status" -eq 1 ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)" = "1" ]
}

@test "two distinct candidates infra → count=2 → HALT" {
  setup_state
  record_infra "c001" || true
  run record_infra "c002"
  [ "$status" -eq 0 ]   # 0 = halt
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)" = "2" ]
}

@test "transient/code-fix success between infra failures resets the gate" {
  setup_state
  record_infra "c001" || true
  reset_infra   # simulates a successful candidate
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)" = "0" ]
  candidates=$("$AUTORESEARCH_BIN/state-read" --slug test-project --path '.consecutive_infra_candidates | length')
  [ "$candidates" = "0" ]
  # New infra after reset starts the count fresh
  run record_infra "c002"
  [ "$status" -eq 1 ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)" = "1" ]
}

@test "code-fix success between infras (reset) prevents premature halt" {
  setup_state
  record_infra "c001" || true
  reset_infra
  record_infra "c002" || true
  # Only count=1 — does NOT halt despite 2 unique candidates ever being infra
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_infra_count)" = "1" ]
}
