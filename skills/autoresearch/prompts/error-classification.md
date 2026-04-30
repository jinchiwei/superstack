# Error classification prompt

You're inside /autoresearch and an experiment iteration just failed. Classify the error so the SKILL.md knows whether to retry, attempt a code-fix, or halt.

**Inputs:**
- `last_iteration.log`: full stdout/stderr from the failed run
- The candidate that was being run (axes)
- Recent error history (count of consecutive failures across recent candidates)

**Output (JSON, no prose):**

```json
{
  "class": "transient|code_bug|infrastructure|unknown",
  "evidence": "<1-2 sentences quoting the part of the log that drove the classification>",
  "suggested_action": "retry|code_fix|halt|skip",
  "retry_adjustment": "<1 sentence describing the adjustment if class=transient — e.g. 'reduce batch size to 8' — else null>",
  "fix_target": "<file:line if class=code_bug, else null>"
}
```

**Classification rules (be liberal toward fight-through):**

- **transient**: CUDA OOM, "Bus error", file lock, transient network failure during data download, intermittent SSH/NFS hiccup, "device-side assert" that's likely flake. Action: retry (up to 3 times in SKILL.md outer loop). Suggest a retry adjustment if obvious.
- **code_bug**: Python traceback whose deepest frame is in user code, AttributeError/NameError/TypeError on user code, ImportError of a project module, IndexError on a tensor reshape. Action: code_fix.
- **infrastructure**: "No space left on device", "CUDA driver version is insufficient", "GPU not found" persisting across retries, "Permission denied" on filesystem write to project, conda env missing. Action: halt.
- **unknown**: when the log doesn't fit any of the above. Action: skip (mark candidate dead, continue with next). Bias toward `unknown→skip` over `unknown→halt` so the loop keeps going.

**Bias rule:** When in doubt between transient and code_bug, choose code_bug — it's better to attempt a fix than to retry a deterministic failure.

When in doubt between code_bug and unknown, choose code_bug if you can identify a specific file:line; else unknown.

When in doubt between infrastructure and anything else, do NOT choose infrastructure unless the evidence is unambiguous. Halting is the worst outcome for the user (they're not present to resolve it). Strongly prefer skip-and-continue.

**Final reminder (D4 consecutive-infra-count gate):** Even if you classify infrastructure, the SKILL.md will not halt until 2 consecutive distinct candidates fail with infra classification. Your single judgment is one signal in a gate, not a halt switch. If uncertain, lean toward `unknown` (skip) — it has the same effect on the next iteration.
