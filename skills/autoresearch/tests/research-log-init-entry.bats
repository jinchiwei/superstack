load helpers

# Setup an isolated research-log repo for these tests. We avoid touching a real
# remote by overriding RESEARCH_LOG_GIT_PUSH=true (no-op).

setup_log_repo() {
  RESEARCH_LOG_ROOT="$TEST_DIR/research-log"
  mkdir -p "$RESEARCH_LOG_ROOT"
  (
    cd "$RESEARCH_LOG_ROOT"
    git init -q
    git config user.email "autoresearch-tests@example.invalid"
    git config user.name "Autoresearch Tests"
    git commit --allow-empty -q -m init
  )
  export RESEARCH_LOG_ROOT
  export RESEARCH_LOG_GIT_PUSH=true
}

@test "research-log-init-entry creates file at expected path with stdin body" {
  setup_log_repo
  body="# Test entry

Body here."
  out=$(printf "%s\n" "$body" | "$AUTORESEARCH_BIN/research-log-init-entry" \
    --top-level brainlab --project test-project --scope-slug demo-sweep)
  [ -f "$out" ]
  # Path conforms to <root>/<top-level>/<project>/YYYY-MM-DD_autoresearch-<slug>.md
  date=$(date +%Y-%m-%d)
  expected="$RESEARCH_LOG_ROOT/brainlab/test-project/${date}_autoresearch-demo-sweep.md"
  [ "$out" = "$expected" ]
  grep -q "# Test entry" "$out"
  grep -q "Body here." "$out"
}

@test "research-log-init-entry commits the new file in research-log repo" {
  setup_log_repo
  printf "# X\n" | "$AUTORESEARCH_BIN/research-log-init-entry" \
    --top-level wolong --project demo --scope-slug s1
  msg=$(cd "$RESEARCH_LOG_ROOT" && git log -1 --pretty=%s)
  [[ "$msg" == *"autoresearch"* ]]
  [[ "$msg" == *"wolong/demo"* ]]
}

@test "research-log-init-entry exits 2 with missing args" {
  setup_log_repo
  run bash -c "echo body | '$AUTORESEARCH_BIN/research-log-init-entry' --top-level x --project y"
  [ "$status" -eq 2 ]
}
