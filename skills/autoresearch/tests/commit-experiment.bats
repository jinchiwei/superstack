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

@test "commit-experiment includes message-suffix when provided" {
  cd "$FAKE_PROJECT"
  echo "x" > result.txt
  run "$AUTORESEARCH_BIN/commit-experiment" --scope-slug demo --iter 4 --candidate c042 --message-suffix "metric=0.81"
  [ "$status" -eq 0 ]
  log=$(git -C "$FAKE_PROJECT" log -1 --pretty=%s)
  [[ "$log" == *"metric=0.81"* ]]
  [[ "$log" == *"iter=4"* ]]
}
