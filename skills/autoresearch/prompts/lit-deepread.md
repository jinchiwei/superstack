# Literature review — full-text deep read (structured extraction) prompt

You are performing the **full-text extraction** pass of a systematic review, on one paper that survived abstract screening. You must decide how this paper actually relates to the session's novelty claim, and extract the evidence that supports that verdict.

**Inputs:**

- `claim_tuple`: the structured decomposition of what this session claims to contribute — normally an object like `{"method": ..., "task": ..., "data": ..., "metric": ...}`, possibly a single line of text. A missing slot is a wildcard, not a mismatch.
- `novelty_claim`: 1-3 sentences stating what would be new about this work relative to prior literature.
- `paper`: metadata in the `bin/lit-search` schema — `{title, authors, year, abstract, url, source}`.
- `fulltext`: the retrieved open-access body text, from `bin/lit_fulltext.py`. **May be absent, empty, or truncated.** The retriever budgets Methods / Materials sections first when it truncates, so what you receive is usually the part that matters most. Section headings appear as `## Heading`. Back matter (references, funding, COI) is already stripped. It may arrive as the raw retriever payload — `{status, text, source, chars, methods_captured}`, where `status` is `ok` / `unavailable` / `error` and `methods_captured` reports whether a methods section made it into `text` — in which case read `text` and use the other fields as described below.

**Output (JSON, no prose):**

```json
{
  "method": "<1-2 sentences: what the paper actually does, in its own terms — architecture, estimator, statistical model, acquisition>",
  "task": "<1-2 sentences: the problem being solved — prediction target, endpoint, comparison>",
  "data": "<1-2 sentences: cohort/dataset name, N, modality, source, splits>",
  "findings": "<1-2 sentences: the headline result WITH the reported numbers and metric names>",
  "relation": "supersedes" | "equivalent" | "overlapping" | "adjacent" | "unrelated",
  "overlap_explanation": "<2-4 sentences naming exactly which claim_tuple slots collide and which differ, justifying the relation label>",
  "killer_quote": "<verbatim quote that would pre-empt the novelty claim, or empty string>",
  "fulltext_used": true | false,
  "confidence": "high" | "medium" | "low"
}
```

**Rules:**

1. **The Methods section decides novelty, not the abstract.** Two papers with near-identical abstracts routinely make entirely different contributions, and the detail that kills a novelty claim is almost always buried in methods — the exact estimator, the preprocessing step, the split strategy, the cohort restriction, the ablation that was actually run. Read `## Methods` / `## Materials and Methods` / `## Experimental Setup` first and weight it above everything else. An abstract that sounds like the claim, contradicted by a methods section that does something else, resolves in favor of the methods section.

2. **Extract on the paper's own terms.** `method`, `task`, `data`, `findings` describe what the paper did — not how it compares to this session. Comparison lives only in `relation` and `overlap_explanation`. Keep the paper's own vocabulary and its own numbers.

3. **`relation` ladder**, decided against `claim_tuple` + `novelty_claim`:
   - `"supersedes"` — the paper already does what the claim says is new, at equal or larger scope (same method class **and** same task, on comparable or broader data). The claim as written is not novel. **Requires a specific methods-level fact stated in `overlap_explanation`.**
   - `"equivalent"` — same method, task, and data class; neither is strictly ahead of the other. A near-duplicate. **Also requires a methods-level fact.**
   - `"overlapping"` — two or more tuple slots collide, but at least one slot that matters differs (different cohort, different endpoint, different estimator family). The claim survives but must be positioned against this paper.
   - `"adjacent"` — one slot in common, or same subfield with a different contribution. Cite for context; no threat to the claim.
   - `"unrelated"` — no meaningful overlap; the paper was a screening false positive. Say so plainly.

4. **`killer_quote` must be verbatim or empty.** Copy a single contiguous span, character for character, from text actually provided to you — no paraphrase, no ellipsis-stitching of separate sentences, no reconstruction from memory. Keep it under ~50 words. Prefer a Methods or Results sentence over an abstract sentence; a claim-killing quote from the abstract alone is weak evidence and must be reflected in `confidence`. If nothing in the text genuinely pre-empts the claim, return `""` — never stretch a quote to fit a `relation` you have already decided on. Do not fabricate a quote under any circumstance; a fabricated quote propagates into the write-up as a citation.

5. **`fulltext_used` is true only when body text beyond the abstract was actually available and used.** If `fulltext` is absent, empty, a retrieval-status placeholder (`unavailable`, `paywalled`, `pdf-unparseable`), or merely a restatement of the abstract, set `fulltext_used: false`.

6. **Abstract-only reads cap `confidence` at `"medium"`, never `"high"`.** An abstract cannot definitively establish that another paper is equivalent to or supersedes this work — the deciding detail lives in methods you did not see. When `fulltext_used` is `false` and you still label the paper `supersedes` or `equivalent`, `overlap_explanation` must name the specific methods detail that remains unverified and would change the verdict.

7. **Truncation handling.** Truncated full text still counts (`fulltext_used: true`). Confidence then depends on what you received: `"high"` only if a methods section was present and the relation is unambiguous; otherwise `"medium"`. When the retriever supplies `methods_captured`, trust it — `methods_captured: false` means the deciding section is missing and confidence is capped at `"medium"` regardless of how long the text is. Do not infer the content of sections you were not given.

8. **`confidence` calibration.** `"high"` = full text including methods, relation unambiguous. `"medium"` = abstract-only, or truncated without methods, or genuine ambiguity about method equivalence. `"low"` = metadata and text disagree, text is not the paper described by `paper`, text is unusable (wrong language, OCR garbage, stub page), or extraction is largely guesswork.

9. **Never emit `null` or `"N/A"`.** Every string field is a non-empty string except `killer_quote`, which is `""` when there is no quote. When the paper genuinely does not report something, write `"not reported"`.

10. **`overlap_explanation` does the analytic work.** Walk the slots explicitly — which of method / task / data / metric collide, which differ, and why that difference does or does not preserve novelty. This is the text a human reads when deciding whether to abandon or reframe the claim; make it decision-grade, and keep every assertion in it traceable to text you were given.

11. **Emit strict JSON only** — no prose before or after, no markdown fence, no comments. All nine keys always present.

12. **Empty / failure case.** If `fulltext` is unusable **and** `paper.abstract` is empty — nothing to read but a title — return exactly this shape, filling `overlap_explanation` with the reason:
    ```json
    {
      "method": "not reported",
      "task": "not reported",
      "data": "not reported",
      "findings": "not reported",
      "relation": "unrelated",
      "overlap_explanation": "No full text and no abstract were available for this paper; relation to the novelty claim could not be assessed from the title alone.",
      "killer_quote": "",
      "fulltext_used": false,
      "confidence": "low"
    }
    ```
    This is a valid result, not an error. Downstream it is recorded as an unresolved candidate rather than a cleared one — do not guess content to avoid it.
