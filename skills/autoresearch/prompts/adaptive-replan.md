# Adaptive replan prompt

You are mid-run in an /autoresearch session. After each iteration, you decide what to try next based on what you've learned so far.

**Inputs:**
- `state.json`: full current state (axes, candidate_queue, results_history, current_best, pivot_history)
- Just-completed iteration's result (or failure)

**Output (JSON, no prose):**

```json
{
  "next_candidate": {
    "id": "c<NNN>",
    "axes": {"arch": "...", "input": "...", ...},
    "priority": <float, higher = more promising>
  } or null if queue should drain naturally,
  "queue_updates": {
    "add": [<new candidates to enqueue>],
    "remove": [<candidate ids to drop from queue>],
    "reprioritize": [{"id": "c<NNN>", "priority": <float>}]
  },
  "pivot": {
    "happened": true|false,
    "from_category": "<axis name>" or null,
    "to_category": "<axis name>" or null,
    "reason": "<one sentence>" or null
  },
  "log_block": "<3-5 line markdown block to append to the research-log entry. Plain prose, no headers.>",
  "promote_to_result_block": "<full markdown ## RESULT block if this iteration was meaningful, else empty string>",
  "rationale": "<2-3 sentences on the strategy update>"
}
```

**Rules:**
1. Adaptive replanning is the whole point. Do NOT just dequeue the next candidate from `candidate_queue` mechanically — actually think about what the results so far suggest. New candidates can deviate from the original axes if results push you to a new hypothesis.
2. **Pivot detection**: a pivot is when next_candidate's primary axis differs from current axis being explored. Set `pivot.happened: true` and write a one-sentence reason. The SKILL.md uses this to add a `## PIVOT` header to the log file.
3. **Meaningful result detection**: a result is meaningful if (a) it's notably better than current_best by >5% on the target metric, (b) it falsifies a hypothesis (whole branch underperforms), or (c) it surprises you. Write the markdown ## RESULT block when meaningful, else empty string.
4. The candidate queue is a hint, not a contract. You can rewrite it.
5. Cap log_block at 5 lines. Be concrete: "Tried unet+t1+mse → val_corr=0.72 (best so far); next: transformer+t1+mse to test arch effect at fixed input/loss."
6. If you have no idea what to try next AND the queue is empty AND nothing in results_history suggests a new axis, output `{"next_candidate": null, ..., "rationale": "search space exhausted"}` — this triggers the exhaustion stop.
7. **Axis ordering is chronological.** If a pivot introduces a new axis dimension that wasn't in the original sweep, **append** it to the existing `axes` dict (don't insert). The end-of-session `_build_xlsx.py` renders Axis Matrix sections top-to-bottom in dict insertion order so the scorecard reads as "tested first → tested last."
