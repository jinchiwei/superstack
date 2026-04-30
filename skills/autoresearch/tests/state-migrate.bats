load helpers

@test "state-migrate is a no-op on a current v1 state" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  before_hash=$(jq -S . "$state_file" | md5sum)
  run "$AUTORESEARCH_BIN/state-migrate" --slug test-project
  [ "$status" -eq 0 ]
  after_hash=$(jq -S . "$state_file" | md5sum)
  [ "$before_hash" = "$after_hash" ]
}

@test "state-migrate exits 1 when no migration is registered for an older schema" {
  # Forge a v0 state.json — there is no migrate_v0_to_v1 registered yet.
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  jq '.schema_version = 0' "$state_file" > "$state_file.tmp" && mv "$state_file.tmp" "$state_file"
  run "$AUTORESEARCH_BIN/state-migrate" --slug test-project
  [ "$status" -eq 1 ]
}

@test "state-migrate exits 3 when schema_version is newer than current" {
  echo '{"scope":"s","scope_slug":"sl","axes":{"a":["x"]},"target_metric":null}' \
    | "$AUTORESEARCH_BIN/state-init" --slug test-project
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  jq '.schema_version = 99' "$state_file" > "$state_file.tmp" && mv "$state_file.tmp" "$state_file"
  run "$AUTORESEARCH_BIN/state-migrate" --slug test-project
  [ "$status" -eq 3 ]
}

@test "state-migrate exits 1 on corrupt state.json" {
  state_file="$FAKE_GSTACK_HOME/projects/test-project/autoresearch/state.json"
  echo "not json" > "$state_file"
  run "$AUTORESEARCH_BIN/state-migrate" --slug test-project
  [ "$status" -eq 1 ]
}
