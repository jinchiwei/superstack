# /autoresearch

Long-running autonomous research loops for Claude Code. Invoke once, walk away for hours or days. Adaptive replanning each iteration, agentic code-fix on failures, optional research-log push, STOP-file kill switch.

## Quick start

```
/autoresearch "iterate over architectures, input modes, and loss functions for the FW prediction model. target: val_corr > 0.85"
```

You'll be asked once to confirm the planned axes, then the loop runs without further prompts.

## Files

- `DESIGN.md` — full design doc + rationale (read this if anything is unclear)
- `IMPLEMENTATION_PLAN.md` — task-by-task build plan (already executed if you're reading this)
- `USAGE.md` — invocation examples + state.json layout + how to halt cleanly
- `SKILL.md` — the skill itself (loaded by Claude Code)
- `bin/` — bash helpers
- `prompts/` — prompt fragments loaded by SKILL.md
- `tests/` — bats tests for the bash helpers

## Status

Built 2026-04-30. v0 — calibration may be needed for prompt tuning on first real run.
