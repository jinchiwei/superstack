# Code-fix proposal prompt

You're inside /autoresearch. The error-classification prompt determined that the last failure was a code_bug. Propose a small Edit to fix it.

**Inputs:**
- `last_iteration.log`: full traceback
- `fix_target`: file:line from the classification
- The actual file content around fix_target (read it before proposing)
- Previous fix attempts on this candidate (max 3 total)

**Output (JSON, no prose):**

```json
{
  "fix_kind": "edit|noop",
  "explanation": "<1 sentence: what's wrong and what your fix does>",
  "edit": {
    "file": "<absolute path>",
    "old_string": "<exact substring to replace, must be unique in file>",
    "new_string": "<replacement>"
  } or null if fix_kind=noop,
  "confidence": <float 0-1>,
  "expected_outcome": "<1 sentence: what should happen on rerun>"
}
```

**Rules:**
1. Stay surgical. Fix the smallest possible thing. Do NOT refactor.
2. The fix must target the specific traceback line. Don't fix unrelated code "while you're there."
3. Common fix patterns:
   - Argument order/name mismatch on a function call
   - Missing import
   - Wrong attribute name on a tensor or module
   - Off-by-one on a slice or reshape
   - dtype/device mismatch (add `.to(device)` or `.float()`)
4. If you've already attempted 2 fixes on this candidate and neither worked, output `{"fix_kind": "noop", "explanation": "two fix attempts failed; marking candidate dead", ...}`.
5. NEVER edit:
   - Configuration files outside the project's source dir
   - Anything under `.git/`, `.gstack/`, `~/.claude/`
   - Files the traceback doesn't directly point at — your fix must be in the file from fix_target.
6. **Working tree safety:** SKILL.md will `git stash` before applying your edit and restore the stash if rerun fails harder. You don't need to worry about cleanup; just propose a clean Edit.
