# Literature review — classify + query design prompt

You are bootstrapping an /autoresearch session. Before the search-space (axes) gets enumerated, decide whether a literature review is appropriate, and if so, propose 2-4 search queries to find relevant prior work.

**Inputs:**
- `scope`: free-text description of the experiment search space (e.g. "iterate over architectures, input modes, loss functions for the FW prediction model")
- `project_context`: a Read of the user's project README/CLAUDE.md/relevant code if useful

**Output (JSON, no prose). One of:**

```json
{
  "skip": true,
  "reason": "<one-sentence reason: e.g. 'QA automation sweep, not a research task'>"
}
```

OR:

```json
{
  "queries": [
    "<focused search query 1>",
    "<focused search query 2>",
    "<query 3 (optional)>",
    "<query 4 (optional)>"
  ],
  "sources": ["pubmed" | "arxiv" | "semanticscholar", ...],
  "focus": "<2-3 sentences naming the specific research question this experiment is trying to answer; this becomes the framing for the synthesis stage>"
}
```

**Rules for the classification (skip vs proceed):**

1. **Permissive default.** When uncertain, proceed with lit review. Most autoresearch sessions are research; only skip when the scope is clearly something else.

2. **Skip cases (be specific in `reason`):**
   - QA / regression test automation across configurations
   - Build matrix exploration (e.g. "test under Python 3.10/3.11/3.12 × Linux/macOS")
   - Performance benchmarking of an internal product where there is no comparable academic literature
   - Configuration sweep purely for ops/deployment tuning
   - Anything where the user is iterating over an artifact they own end-to-end with no expectation of a publishable contribution

3. **Proceed cases (the 95% default):**
   - Model architecture / hyperparameter / loss / input-modality sweeps in ML
   - Algorithm selection or comparison
   - Biomedical/scientific experiments (datasets, statistical methods, biomarkers, etc.)
   - Anything where similar work has likely been published and could inform the search space or strengthen the novelty claim

**Rules for query design (when proceeding):**

4. **2-4 queries.** Each should be 4-10 words, focused on a different facet:
   - One query naming the **method/architecture** in the scope
   - One query naming the **task/dataset/domain**
   - Optionally a query for adjacent prior approaches that might constrain or inspire axes
   - Optionally a query naming a specific known prior baseline if the scope mentions one
   - Avoid bare buzzword queries like "deep learning" — they will return noise

5. **Source selection.** Default to `["pubmed", "arxiv", "semanticscholar"]`. Override only when one source is obviously irrelevant:
   - Pure ML/CS work with no biomedical signal: drop `pubmed`
   - Clinical/biomedical with no compute angle: drop `arxiv`
   - Always keep `semanticscholar` — it cross-cuts both

6. **Focus statement.** Write 2-3 sentences naming what specifically would constitute novelty for this experiment relative to known prior work. This is the "what would we be adding to the literature?" framing. The downstream synthesizer uses this to anchor its prior-work / novelty narrative.

7. **If the scope is incoherent** (uninterpretable, contradictory, missing critical context): return `{"skip": true, "reason": "<reason>"}` rather than guessing queries. Better to skip than produce noise.
