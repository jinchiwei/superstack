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

@test "state-init schema includes new D1-D4 fields" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  # D1: pending_stash_ref starts null
  [ "$(jq -r .pending_stash_ref "$state_file")" = "null" ]
  # D2: consecutive_iteration_failures = 0, last_error_at = null
  [ "$(jq -r .consecutive_iteration_failures "$state_file")" = "0" ]
  [ "$(jq -r .last_error_at "$state_file")" = "null" ]
  # D4: consecutive_infra_count = 0, consecutive_infra_candidates = []
  [ "$(jq -r .consecutive_infra_count "$state_file")" = "0" ]
  [ "$(jq -r '.consecutive_infra_candidates | length' "$state_file")" = "0" ]
  # Folded fix #2: last_modified_at and last_iteration_completed_at
  [ "$(jq -r 'has("last_modified_at")' "$state_file")" = "true" ]
  [ "$(jq -r 'has("last_iteration_completed_at")' "$state_file")" = "true" ]
}

@test "state-read returns nested field via jq path" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  run "$AUTORESEARCH_BIN/state-read" --slug test-project --path .scope_slug
  [ "$status" -eq 0 ]
  [ "$output" = "sl" ]
}

@test "state-update modifies a field and auto-touches last_modified_at" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  before=$(jq -r .last_modified_at "$state_file")
  sleep 1
  "$AUTORESEARCH_BIN/state-update" --slug test-project --set '.phase = "running"'
  run "$AUTORESEARCH_BIN/state-read" --slug test-project --path .phase
  [ "$output" = "running" ]
  after=$(jq -r .last_modified_at "$state_file")
  [ "$before" != "$after" ]
}

@test "state-validate exits 0 on valid state" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  run "$AUTORESEARCH_BIN/state-validate" --slug test-project
  [ "$status" -eq 0 ]
}

@test "state-validate exits 1 on corrupt JSON" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  echo "not json" > "$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  run "$AUTORESEARCH_BIN/state-validate" --slug test-project
  [ "$status" -eq 1 ]
}

@test "state-validate exits 2 on schema older than current" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  # Force schema_version to 0 (older)
  jq '.schema_version = 0' "$state_file" > "$state_file.tmp" && mv "$state_file.tmp" "$state_file"
  run "$AUTORESEARCH_BIN/state-validate" --slug test-project
  [ "$status" -eq 2 ]
}

@test "state-validate exits 3 on schema newer than current" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  jq '.schema_version = 99' "$state_file" > "$state_file.tmp" && mv "$state_file.tmp" "$state_file"
  run "$AUTORESEARCH_BIN/state-validate" --slug test-project
  [ "$status" -eq 3 ]
}

@test "state-update fails non-zero when state dir is unwritable" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_dir="$FAKE_GSTACK_HOME/projects/test-project/autoresearch"
  chmod -w "$state_dir"
  run "$AUTORESEARCH_BIN/state-update" --slug test-project --set '.phase = "running"'
  chmod +w "$state_dir"
  [ "$status" -ne 0 ]
}
