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
