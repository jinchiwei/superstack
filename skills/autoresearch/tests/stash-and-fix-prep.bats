load helpers

# Per T1 (locked in /plan-eng-review): cover clean tree, dirty tree, untracked-only,
# pop-after-fail end-to-end, drop-after-success end-to-end.

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

@test "drop-after-success keeps the fix and cleans up the stash" {
  cd "$FAKE_PROJECT"
  echo "v1" > target.py && git add target.py && git commit -q -m base
  echo "user-edit" >> target.py
  STASH_REF=$("$AUTORESEARCH_BIN/stash-and-fix-prep")
  [ "$STASH_REF" != "__CLEAN__" ]

  # Apply the fix
  echo "good-fix" >> target.py

  # Simulate rerun success: commit the fix, then drop the stash
  git add target.py && git commit -q -m fix
  git stash drop "$STASH_REF" >/dev/null

  # Stash list should be empty for our autoresearch entries
  count=$(git stash list | grep -c "autoresearch:code-fix-prep" || true)
  [ "$count" = "0" ]
  # The committed fix is in HEAD
  git log -1 --pretty=%s | grep -q "fix"
}
