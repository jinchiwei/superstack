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
