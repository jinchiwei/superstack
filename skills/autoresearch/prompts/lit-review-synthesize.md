# Literature review — synthesis prompt

You have run focused literature searches and collected abstracts of prior work. Synthesize what you found into a structured summary that frames the user's experiment relative to the existing literature.

**Inputs:**
- `scope`: the original free-text scope of the autoresearch session
- `focus`: the 2-3 sentence "what would constitute novelty?" framing from the classification stage
- `project_context`: brief project background (CLAUDE.md / README extract)
- `papers`: a JSON list of papers from `bin/lit-search`, each with `{title, authors, year, abstract, url, source}`. May contain partial or empty abstracts; not every paper will be relevant.

**Output (JSON, no prose):**

```json
{
  "prior_work_summary": "<3-5 sentences on the dominant approaches and findings in the literature most relevant to this scope>",
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
  "novelty_argument": "<2-3 sentences naming what THIS experiment adds vs. the literature. Be specific. Reference the gap(s) the experiment addresses. If the experiment is largely a replication or non-novel, say so honestly.>",
  "top_relevant": [
    {
      "title": "<paper title>",
      "year": <int or null>,
      "url": "<url>",
      "why_relevant": "<one line: how it relates to the user's scope>"
    }
    // 3-7 entries, ordered by relevance
  ],
  "axis_implications": "<1-2 sentences naming any axis values the literature suggests including or excluding (e.g. 'transformers consistently outperform CNNs on this task per refs [1,3]; consider adding a transformer baseline'). Empty string if no clear implications.>"
}
```

**Rules:**

1. **Be honest about novelty.** If the literature already covers what the user is proposing, say so. The user prefers an honest "this is largely a replication of [refs]" over an inflated novelty claim. The point is to inform the user before they spend hours on a sweep, not to bless the sweep.

2. **Filter for relevance.** Not every paper returned by `bin/lit-search` will be on-target. Use only the papers whose abstracts substantively connect to the scope. It's fine to return only 3 `top_relevant` entries if 7 weren't actually relevant.

3. **`top_relevant` ordering.** Order by relevance to scope, not by year or citation count. The first entry should be the single most directly comparable prior work.

4. **`axis_implications` is the bridge.** This is what gets passed to the axis-enumeration prompt next. Keep it concrete: "include X", "exclude Y", "consider adding Z". Empty string is acceptable when the literature doesn't strongly constrain the axis design.

5. **Length budget.** Total output should fit in ~400 tokens. The user sees this in a confirmation prompt before launch — don't overwhelm.

6. **Citations format.** When referencing papers in narrative fields (`prior_work_summary`, `novelty_argument`, `axis_implications`), use bracket notation `[1]`, `[2]`, etc., where the number is the 1-indexed position in the `top_relevant` list. This lets the downstream renderer link them.

7. **Empty result handling.** If `papers` is empty or contains nothing relevant, return:
   ```json
   {
     "prior_work_summary": "Literature search returned no clearly relevant prior work for this scope.",
     "dominant_approaches": [],
     "gaps": [],
     "novelty_argument": "<best-effort framing of why this work might be of interest, framed honestly given the absence of comparable prior literature in the search results>",
     "top_relevant": [],
     "axis_implications": ""
   }
   ```
   This is rare but not an error — the user still proceeds, the research-log entry just notes "no comparable prior work found in <sources>".
