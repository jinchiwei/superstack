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
