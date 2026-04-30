load helpers

setup_log_repo() {
  RESEARCH_LOG_ROOT="$TEST_DIR/research-log"
  mkdir -p "$RESEARCH_LOG_ROOT"
  (
    cd "$RESEARCH_LOG_ROOT"
    git init -q
    git commit --allow-empty -q -m init
  )
  export RESEARCH_LOG_ROOT
  export RESEARCH_LOG_GIT_PUSH=true
}

@test "research-log-append appends stdin block with leading blank lines" {
  setup_log_repo
  printf "# Initial\n" | "$AUTORESEARCH_BIN/research-log-init-entry" \
    --top-level brainlab --project p1 --scope-slug s1 >/dev/null
  date=$(date +%Y-%m-%d)
  file="$RESEARCH_LOG_ROOT/brainlab/p1/${date}_autoresearch-s1.md"
  printf "iter 1 — val_corr=0.72\n" | "$AUTORESEARCH_BIN/research-log-append" \
    --file "$file" --commit-message "autoresearch: iter 1"
  grep -q "iter 1 — val_corr=0.72" "$file"
  # Two newlines between original body and appended block
  awk '/^# Initial/{init=1} init && /iter 1/{found=1} END{exit found?0:1}' "$file"
}

@test "research-log-append commits with provided message" {
  setup_log_repo
  printf "# Initial\n" | "$AUTORESEARCH_BIN/research-log-init-entry" \
    --top-level brainlab --project p1 --scope-slug s1 >/dev/null
  date=$(date +%Y-%m-%d)
  file="$RESEARCH_LOG_ROOT/brainlab/p1/${date}_autoresearch-s1.md"
  printf "block\n" | "$AUTORESEARCH_BIN/research-log-append" \
    --file "$file" --commit-message "autoresearch: iter 7 — note"
  msg=$(cd "$RESEARCH_LOG_ROOT" && git log -1 --pretty=%s)
  [ "$msg" = "autoresearch: iter 7 — note" ]
}

@test "research-log-append exits 2 with missing args" {
  setup_log_repo
  run bash -c "echo block | '$AUTORESEARCH_BIN/research-log-append' --file /tmp/x"
  [ "$status" -eq 2 ]
}
