# tests/helpers.bash
# Common setup/teardown for bats tests.

setup() {
  # Each test runs in an isolated temp dir
  TEST_DIR=$(mktemp -d)
  export TEST_DIR
  export FAKE_GSTACK_HOME="$TEST_DIR/gstack"
  export FAKE_PROJECT="$TEST_DIR/project"
  mkdir -p "$FAKE_GSTACK_HOME/projects/test-project/autoresearch" "$FAKE_PROJECT"
  cd "$FAKE_PROJECT" && git init -q && git commit --allow-empty -q -m "init"
  cd - >/dev/null
  export AUTORESEARCH_BIN="$BATS_TEST_DIRNAME/../bin"
  export GSTACK_HOME="$FAKE_GSTACK_HOME"
}

teardown() {
  rm -rf "$TEST_DIR"
}
