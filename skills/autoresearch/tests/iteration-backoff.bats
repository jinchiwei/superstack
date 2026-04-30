load helpers

# These tests verify the math + state transitions the SKILL.md RUNNING-mode
# wrapper performs on iteration error (D2 LOCKED). They exercise the
# state-update bash invocations directly so the contract is regression-safe
# even if SKILL.md prose is rephrased later.

# Helper: simulate one wrapped iteration error — bumps consecutive_iteration_failures,
# sets last_error_at, computes the backoff delay the SKILL.md must use.
simulate_iteration_error() {
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set '
    .consecutive_iteration_failures += 1
    | .last_error_at = (now | todateiso8601)
  '
  n=$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_iteration_failures)
  delay=$(( 1800 * (1 << (n - 1)) ))
  [[ "$delay" -gt 3600 ]] && delay=3600
  echo "$delay"
}

# Helper: simulate a successful iteration — resets counter, sets last_iteration_completed_at.
simulate_iteration_success() {
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set '
    .consecutive_iteration_failures = 0
    | .last_iteration_completed_at = (now | todateiso8601)
  '
}

setup_state() {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project >/dev/null
}

@test "first iteration error sets failures=1 and delay=1800s" {
  setup_state
  delay=$(simulate_iteration_error)
  [ "$delay" = "1800" ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_iteration_failures)" = "1" ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .last_error_at)" != "null" ]
}

@test "second consecutive error sets failures=2 and delay=3600s (capped)" {
  setup_state
  simulate_iteration_error >/dev/null
  delay=$(simulate_iteration_error)
  [ "$delay" = "3600" ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_iteration_failures)" = "2" ]
}

@test "third+ consecutive error stays at delay=3600s (cap holds)" {
  setup_state
  simulate_iteration_error >/dev/null
  simulate_iteration_error >/dev/null
  delay=$(simulate_iteration_error)
  [ "$delay" = "3600" ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_iteration_failures)" = "3" ]
  delay=$(simulate_iteration_error)
  [ "$delay" = "3600" ]
}

@test "successful iteration resets failures to 0" {
  setup_state
  simulate_iteration_error >/dev/null
  simulate_iteration_error >/dev/null
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_iteration_failures)" = "2" ]
  simulate_iteration_success
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .consecutive_iteration_failures)" = "0" ]
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .last_iteration_completed_at)" != "null" ]
}

@test "phase remains running across iteration errors (D2: do NOT halt on caught errors)" {
  setup_state
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set '.phase = "running"'
  simulate_iteration_error >/dev/null
  simulate_iteration_error >/dev/null
  simulate_iteration_error >/dev/null
  [ "$("$AUTORESEARCH_BIN/state-read" --slug test-project --path .phase)" = "running" ]
}
