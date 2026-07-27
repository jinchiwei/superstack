# Novelty synthesis — final verdict prompt

You have run a multi-round literature investigation against a specific novelty claim: queries across several sources, citation-graph snowballing, full-text deep reads where open access allowed, and a per-lens assessment of each dimension of the claim. This is the terminal stage. Produce the verdict the user sees **before** they spend hours on a sweep.

This prompt replaces `prompts/lit-review-synthesize.md`. It preserves that file's downstream contract: `axis_implications` is consumed by `prompts/axis-enumeration.md`, and `top_relevant` + `prior_work_summary` + `novelty_argument` are rendered into the research-log `## Prior work & novelty` section and the Step 4 confirmation prompt. Those four fields keep their names and their meaning exactly.

**Inputs:**

- `novelty_claim`: the one-sentence claim under test (e.g. "a graph transformer over free-water DTI features predicts APOE4 dose better than region-wise regression in ADNI").
- `claim_tuple`: the structured decomposition of that claim — typically `{method, data, population, outcome, comparator, scale}`, with `null` for dimensions the claim does not commit to. Fields not present are simply not claimed, and cannot be a source of novelty.
- `deep_reads`: list of the papers that were read past the abstract. Each entry carries the `bin/lit-search` paper dict (`{title, authors, year, abstract, url, source}`), a `fulltext` block from `bin/lit_fulltext.py` (`{status: "ok"|"unavailable"|"error", source, chars}`), and extracted notes. `status != "ok"` means **abstract-only** — the methods section was never seen.
- `verdicts`: per-lens judgments, one per dimension of `claim_tuple` that was testable. Each names the `lens`, a judgment (covered / partially covered / uncovered), the papers that drove it, and notes.
- `search_coverage`: `{sources_queried: [str], query_count: int, papers_found: int, papers_screened: int, deep_read_count: int, rounds_run: int, saturation_reached: bool}` plus any notes on sources that errored, rate-limited, or were deliberately skipped.

**Output (JSON, no prose):**

```json
{
  "prior_work_summary": "<3-5 sentences on the dominant approaches and findings in the literature most relevant to this claim>",
  "dominant_approaches": [
    "<one-line description of approach pattern 1, e.g. 'CNN backbones with cross-entropy loss on labeled MRI'>",
    "<approach pattern 2>",
    "<approach pattern 3 (optional)>"
  ],
  "gaps": [
    "<one-sentence underexplored direction 1>",
    "<gap 2>",
    "<gap 3 (optional)>"
  ],
  "novelty_argument": "<2-3 sentences naming what THIS work adds vs. the literature, with [n] citations. Be specific. If it is largely a replication, say that outright.>",
  "top_relevant": [
    {
      "title": "<paper title>",
      "year": <int or null>,
      "url": "<url>",
      "why_relevant": "<one line: how it relates to the claim>"
    }
  ],
  "axis_implications": "<1-2 sentences naming axis values the literature suggests including or excluding (e.g. 'transformers consistently outperform CNNs on this task per [1,3]; add a transformer baseline'). Empty string if no clear implications.>",
  "verdict": "novel-method" | "novel-application" | "novel-data" | "novel-scale" | "incremental" | "replication",
  "nearest_prior_work": {"title": "<title>", "url": "<url>", "year": <int or null>},
  "delta": "<precisely what THIS adds over nearest_prior_work — one or two sentences, concrete and checkable; empty-ish hedges are a failure>",
  "confidence": "high" | "medium" | "low",
  "what_would_change_this": [
    "<concrete check 1 that would move the verdict, e.g. 'full text of [2], which was paywalled'>",
    "<check 2>"
  ],
  "coverage_caveat": "<plain statement of what was and was NOT searched: sources queried, rounds run, saturation, paywalled full text, languages, date bounds>"
}
```

`nearest_prior_work` is `null` **only** when `top_relevant` is empty.

**Rules:**

1. **Be blunt about replication.** If the literature already covers the claim, return `"replication"` or `"incremental"` and say so in `novelty_argument` in those words: "this is largely a replication of [1], which used the same method on the same cohort." The user has explicitly asked for that over an inflated claim. The point of this stage is to inform **before** hours are spent, not to bless the sweep. A verdict of `replication` is a successful, useful output — never soften it to `novel-scale` because the sweep is already planned.

2. **Verdict taxonomy — pick exactly one.**
   - `novel-method` — the algorithm / estimator / architecture itself is new or materially modified, not merely re-parameterized.
   - `novel-application` — an established method applied to a task, modality, or population where it has not been reported.
   - `novel-data` — a cohort, measurement, or dataset that has not previously been assembled or analyzed for this question.
   - `novel-scale` — same method and application as prior work, at materially larger N / compute / breadth. State the factor in `delta` (e.g. "1,192 subjects vs. 84 in [1]"); if you cannot state a factor, this is not `novel-scale`.
   - `incremental` — a variant, tuning, or ablation of established work; the delta is real but small.
   - `replication` — substantively the same claim as existing work; the contribution is confirmation.

   **Tie-break toward the less novel label.** When two labels are defensible on the evidence, choose the one that claims less.

3. **`delta` must be precise.** Name the specific dimension of `claim_tuple` that differs from `nearest_prior_work` and how. "Uses a different architecture" is a failure; "replaces [1]'s region-wise ridge regression with a graph transformer over the same 68 Desikan regions, on 3× the subjects" is correct. If the delta is only "we run it ourselves," say exactly that — that is the full content of a `replication` verdict.

4. **`confidence` caps (mechanical, not judgment calls).**
   - Cap at `"medium"` if `search_coverage.saturation_reached` is false.
   - Cap at `"medium"` if more than half of `deep_reads` have `fulltext.status != "ok"` (abstract-only reads cannot rule out a methods-section match).
   - Cap at `"low"` if `deep_read_count` is 0, or if only one source was successfully queried, or if `top_relevant` is empty.
   - `"high"` requires saturation reached, majority full-text deep reads, and at least two sources queried. It is uncommon — do not default to it.
   - Caps compose: apply the strictest one that fires.

5. **`coverage_caveat` states recall limits objectively.** Recall is never provable — a claim of "nothing exists" is a claim about the searches, not about the literature. Name the real gaps concretely: which sources were queried and which were not, how many rounds ran and whether saturation was reached, how many deep reads hit paywalls (`fulltext.status` of `unavailable` / `error`), that only English-language indexed work was reachable, and any date bounds. Do not use the word "honest" or "honestly" — state what was and was not covered and let the facts carry it. Example shape: "5 queries across PubMed, OpenAlex, and Europe PMC over 2 rounds; saturation reached. 4 of 11 deep reads were paywalled, so their methods sections were never seen. arXiv was not queried; non-English and non-indexed work was out of reach."

6. **`what_would_change_this` is a to-do list, not a disclaimer.** 2-4 entries, each a specific, executable check whose outcome would move `verdict` or `confidence`: "full text of [2], which was paywalled"; "a PubMed search for '<specific term>', which was never issued"; "confirming whether [1]'s cohort excludes APOE4 homozygotes." No generic "more searching could reveal more."

7. **Filter for relevance.** Not every retrieved paper belongs in `top_relevant`. Use only papers that substantively bear on the claim. 3 entries is fine if 7 were not actually relevant. Order by relevance to the claim, not by year or citation count — entry 1 is the single most directly comparable prior work, and it is normally the same paper as `nearest_prior_work`. If it is not, `novelty_argument` must explain why.

8. **Citations format.** In every narrative field (`prior_work_summary`, `novelty_argument`, `axis_implications`, `delta`, `what_would_change_this`, `coverage_caveat`), cite with bracket notation `[1]`, `[2]` — 1-indexed positions in `top_relevant`. Never cite an index that does not exist in `top_relevant`, and never cite a paper by name without its bracket. The downstream renderer resolves these to links.

9. **`axis_implications` is the bridge — unchanged.** It is passed verbatim to `prompts/axis-enumeration.md` as `lit_review_summary`. Keep it concrete and advisory: "include X", "exclude Y", "add Z as a baseline". Empty string is acceptable when the literature does not constrain the axis design. Do not put the verdict, the caveat, or apologetics here — the axis prompt reads it as design guidance only.

10. **Ground every claim in the inputs.** Every statement in `prior_work_summary`, `verdicts` reasoning, and `delta` must trace to a paper in `deep_reads` or `top_relevant`. Do not assert what a paper did from its title alone; if only the abstract was read, phrase it as what the abstract reports. Never invent a citation, a year, or a URL.

11. **Length budget.** ~600 tokens total. The user reads this in the Step 4 confirmation prompt before launch. `prior_work_summary` ≤ 5 sentences; `novelty_argument` ≤ 3; `delta` ≤ 2; `coverage_caveat` ≤ 3.

12. **Empty result handling.** If nothing relevant was found, absence of hits is weak evidence — it does not license a `novel-*` verdict on its own. Return:
    ```json
    {
      "prior_work_summary": "Multi-round search returned no clearly relevant prior work for this claim.",
      "dominant_approaches": [],
      "gaps": [],
      "novelty_argument": "<best-effort framing of why this work might be of interest, stated plainly given the absence of comparable prior literature in the search results>",
      "top_relevant": [],
      "axis_implications": "",
      "verdict": "<the best-supported label; do not claim novel-* on absence of hits alone — prefer the least-claiming label the evidence supports>",
      "nearest_prior_work": null,
      "delta": "No comparable prior work was retrieved, so no delta can be computed against a named reference.",
      "confidence": "low",
      "what_would_change_this": ["<specific unissued query or unqueried source 1>", "<check 2>"],
      "coverage_caveat": "<which sources were queried, how many rounds, saturation status, and the plain statement that a null result here reflects the searches run, not the literature>"
    }
    ```
    This is rare but not an error — the session still proceeds, and the research-log entry notes "no comparable prior work found in <sources>".

13. **Malformed or missing inputs.** If `novelty_claim` is empty or `claim_tuple` is unusable, return `{"error": "<one-sentence reason>"}` instead of guessing. The SKILL.md failure path treats novelty synthesis as non-essential and proceeds without it — never block the session.
