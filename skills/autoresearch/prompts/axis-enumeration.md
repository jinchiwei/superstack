# Axis enumeration prompt

You are bootstrapping an /autoresearch session. The user gave you a free-text scope describing what to explore. Convert it into a concrete experiment search space.

**Inputs:**
- `scope`: free-text description (e.g. "iterate over architectures, input modes, loss functions for the FW prediction model")
- `project_context`: a Read of the user's project README/CLAUDE.md/relevant code if useful

**Outputs (JSON, no prose):**

```json
{
  "scope_slug": "<2-3 hyphenated words capturing the search domain>",
  "target_metric": {"name": "<metric>", "op": ">|<|>=|<=|=", "threshold": <number>} or null if user did not specify,
  "axes": {
    "<category1>": ["<value1>", "<value2>", ...],
    "<category2>": ["<value1>", ...]
  },
  "rationale": "<1-2 sentences on why these axes were chosen>"
}
```

**Rules:**
1. Each axis is a category with 2-8 concrete options. Don't enumerate continuous ranges as discrete values unless the user named them.
2. Stick close to what the scope says. Don't invent unrelated dimensions.
3. If the user named a target metric in the scope ("until val_corr > 0.85"), parse it. If not, set target_metric to null and rely on exhaustion-stop.
4. scope_slug is filename-safe (lowercase, hyphens, no special chars). Should make sense as a research-log entry slug.
5. If you can't make sense of the scope, return `{"error": "<one-sentence reason>"}` instead — the SKILL.md handles the error path.

**Cardinality budget:**
The full Cartesian product of axes is the worst-case search space. Keep it under ~50 cells unless the scope explicitly asks for exhaustive sweep. If the product would exceed 50, propose smaller axis vocabularies.

**Output-path convention:**
The autoresearch skill organizes outputs as:
- `results/<YYYY-MM-DD>_<scope_slug>/iter-<NN>_<candidate-slug>/` — synthesized outputs (figures, summary.md, csv) — committed
- `exp/<YYYY-MM-DD>_<scope_slug>/iter-<NN>_<candidate-slug>/` — raw artifacts (checkpoints, large logs) — gitignored

When you write the per-iteration experiment command in SKILL.md Step 3, your candidate scripts MUST honor two env vars exported by the skill:
- `$AUTORESEARCH_OUT_RESULTS` — the results dir for this iteration (always exists when the script runs)
- `$AUTORESEARCH_OUT_EXP` — the exp dir for this iteration (always exists)

Each iteration MUST write a `summary.md` into `$AUTORESEARCH_OUT_RESULTS/summary.md` so downstream report builders can find it.
