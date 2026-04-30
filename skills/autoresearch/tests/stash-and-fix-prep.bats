load helpers

# Per T1 (locked in /plan-eng-review): cover clean tree, dirty tree, untracked-only,
# pop-after-fail end-to-end, pop-after-success end-to-end.
#
# (Per /codex review P1-1, the post-success path uses `git stash pop`, NOT
# `git stash drop`. The earlier "drop-after-success" test encoded a data-loss bug:
# dropping the stash silently discards the user's pre-existing uncommitted work.)

@test "stash-and-fix-prep emits __CLEAN__ on a clean working tree" {
  cd "$FAKE_PROJECT"
  run "$AUTORESEARCH_BIN/stash-and-fix-prep"
  [ "$status" -eq 0 ]
  [ "$output" = "__CLEAN__" ]
}

@test "stash-and-fix-prep emits a real stash ref on a dirty tracked tree" {
  cd "$FAKE_PROJECT"
  echo "tracked" > a.txt && git add a.txt && git commit -q -m a
  echo "dirty" >> a.txt
  # Stash chatter goes to stderr; capture stdout only.
  output=$("$AUTORESEARCH_BIN/stash-and-fix-prep" 2>/dev/null)
  [[ "$output" =~ ^stash@\{[0-9]+\}$ ]]
  [ "$output" != "__CLEAN__" ]
  # tree is now clean post-stash
  cd "$FAKE_PROJECT" && git diff --quiet
}

@test "stash-and-fix-prep emits a real stash ref when only untracked files exist" {
  cd "$FAKE_PROJECT"
  echo "new" > untracked.txt
  output=$("$AUTORESEARCH_BIN/stash-and-fix-prep" 2>/dev/null)
  [[ "$output" =~ ^stash@\{[0-9]+\}$ ]]
  [ ! -f "$FAKE_PROJECT/untracked.txt" ]
}

@test "pop-after-fail restores prior dirty state when fix is reverted" {
  cd "$FAKE_PROJECT"
  echo "v1" > target.py && git add target.py && git commit -q -m base
  echo "user-edit" >> target.py            # uncommitted user work
  STASH_REF=$("$AUTORESEARCH_BIN/stash-and-fix-prep")
  [ "$STASH_REF" != "__CLEAN__" ]

  # Simulate a code-fix Edit
  echo "broken-fix" >> target.py
  # Simulate rerun failure path: revert the bad fix file, then pop the stash
  git checkout -- target.py
  git stash pop "$STASH_REF" >/dev/null

  # Original user-edit should be restored
  grep -q "user-edit" target.py
  ! grep -q "broken-fix" target.py
}

@test "pop-after-success commits the fix and restores user's prior work" {
  cd "$FAKE_PROJECT"
  # Realistic scenario: the LLM-proposed fix is on target.py; the user's pre-existing
  # work is in OTHER files. (When user-edit and fix touch the same lines, git stash pop
  # produces conflict markers — that's an acceptable degradation; data is preserved
  # in the stash, just not auto-merged. Drop would silently destroy it.)
  echo "v1" > target.py && git add target.py && git commit -q -m base
  echo "user-notes" > notes.md                  # untracked user file
  echo "config" > config.yaml && git add config.yaml && git commit -q -m base2
  echo "user-config-edit" >> config.yaml        # uncommitted user edit on tracked file

  STASH_REF=$("$AUTORESEARCH_BIN/stash-and-fix-prep")
  [ "$STASH_REF" != "__CLEAN__" ]
  # tree is clean post-stash
  git diff --quiet
  [ ! -f notes.md ]
  ! grep -q "user-config-edit" config.yaml

  # Apply the fix on the clean tree (LLM edits ONLY target.py, per code-fix.md rules)
  echo "good-fix" >> target.py

  # Simulate rerun success: commit ONLY the fix, then POP the stash (do NOT drop).
  git add target.py && git commit -q -m fix
  git stash pop "$STASH_REF" >/dev/null

  # The committed fix is in HEAD
  git log -1 --pretty=%s | grep -q "fix"
  grep -q "good-fix" target.py
  # The user's prior uncommitted work has been restored to the working tree
  [ -f notes.md ] && grep -q "user-notes" notes.md
  grep -q "user-config-edit" config.yaml

  # Autoresearch stash entry has been consumed by the pop, not dropped
  count=$(git stash list | grep -c "autoresearch:code-fix-prep" || true)
  [ "$count" = "0" ]
}
