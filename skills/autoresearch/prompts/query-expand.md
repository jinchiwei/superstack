# Query expansion prompt

You are generating the search queries for one round of an /autoresearch literature sweep. The objective is **recall, not precision** — a downstream classifier filters noise, but nothing recovers a paper that was never retrieved. A missed paper is a scooped project; a noisy hit costs one line of triage.

The design principle: **each query should be blind to what the others miss.** A single well-crafted query fails silently — it returns fifteen plausible papers and you never learn about the one indexed under different vocabulary, in an adjacent disease, or by a group that names the method after itself. So generate many queries along *different axes*, phrased in *different vocabularies*, routed to *different sources*, and let their union cover the claim.

**Inputs:**
- `claim_tuple`: `{method, task, data, outcome}` from `prompts/novelty-frame.md`
- `novelty_claim`: the one-sentence falsifiable claim whose novelty is at stake
- `round`: integer, 1-indexed. Round 1 is the cold start; later rounds run after a completeness critic has reviewed what round 1 found.
- `already_tried`: list of query strings issued in all previous rounds. Empty on round 1.
- `critic_hints`: free-text gap notes from the completeness critic (e.g. "no non-English-language work retrieved", "nothing from the NODDI/bi-tensor camp", "all hits post-2020; earlier method papers missing"). Empty on round 1.

**Output (JSON, no prose):**

```json
{
  "queries": [
    {
      "axis": "method",
      "query": "<3-10 word keyword phrase>",
      "sources": ["arxiv", "semanticscholar", "openalex"]
    },
    {
      "axis": "data",
      "query": "<another query, different vocabulary>",
      "sources": ["pubmed", "europepmc"]
    }
    // 15-30 entries total, see Rule 1 for axis coverage minimums
  ],
  "synonyms": {
    "<concept from claim_tuple>": ["<alias>", "<acronym>", "<expansion>", "<MeSH term>", "<near-neighbor method>"],
    "<second concept>": ["<alias>", "..."]
  }
}
```

**Rules:**

1. **15-30 queries, spanning at least 5 of the 7 axes.** Minimum 2 queries per axis you use; `method`, `task`, and `data` are mandatory axes. Fewer than 15 queries is a failed round — a thin query set is exactly the silent failure this stage exists to prevent.

   | `axis` | what it hunts | typical phrasing |
   |---|---|---|
   | `method` | the technique itself, wherever applied | "bi-tensor free water elimination diffusion MRI" |
   | `task` | the inference problem, method-agnostic | "preoperative molecular subtype prediction brain tumor" |
   | `data` | the cohort / modality / registry | "NACC diffusion MRI harmonization multisite" |
   | `outcome` | the endpoint / label / biomarker | "MGMT promoter methylation imaging correlate" |
   | `group` | the lab or consortium that owns the problem — people index their own work by their own names | "Pasternak free water imaging", "ADNI DTI core" |
   | `venue` | reviews, meta-analyses, benchmark papers, proceedings — the fastest route to a field's back catalog | "systematic review radiomics CNS lymphoma", "MICCAI diffusion microstructure challenge" |
   | `adjacent` | same method, different disease; same task, different modality; same outcome, different field — **where scoops hide** | "radiomics MGMT glioblastoma" when the claim is about PCNSL |

2. **Synonym / alias / MeSH expansion is mandatory, and it feeds the queries.** Populate `synonyms` with an entry for each substantive concept in `claim_tuple`, then actually *use* those aliases across different `queries` entries — two queries that differ only in word order are one query.
   - **Expand acronyms in both directions.** "FW" → "free water"; "primary CNS lymphoma" → "PCNSL"; "NODDI" → "neurite orientation dispersion and density imaging". Papers are indexed inconsistently, and the acronym-only paper and the expansion-only paper are different papers.
   - **Include method near-neighbors, not just literal aliases.** For "free water": `free water`, `FW`, `free-water elimination`, `bi-tensor`, `two-compartment diffusion model`, `FWE-DTI`, `NODDI`, `extracellular volume fraction`. A reader would call several of these the same idea; the indexes do not.
   - **Include MeSH / controlled-vocabulary terms for biomedical concepts** (e.g. "Diffusion Tensor Imaging", "Lymphoma, Non-Hodgkin", "Alzheimer Disease"). These are what PubMed and Europe PMC actually index on, and they often differ sharply from how authors phrase things in titles.
   - **Include the deprecated / historical name** where a field renamed something ("mild cognitive impairment" vs "prodromal AD"; "MRSI" vs "chemical shift imaging"). Pre-rename papers are invisible to post-rename vocabulary.

3. **Route each query to the sources that actually index it.** `sources` is a list of 1-4 entries drawn from: `pubmed`, `arxiv`, `semanticscholar`, `openalex`, `europepmc`, `crossref`, `biorxiv`. Do not send every query to every source — it multiplies rate-limit pressure without adding recall.
   - `pubmed` — clinical / biomedical, MeSH-indexed. Use for `data`, `outcome`, clinical `task` queries.
   - `europepmc` — biomedical plus preprints, and it searches full text, so it catches methods named only in a Methods section. Pair with `pubmed`, never a substitute for it.
   - `arxiv` — ML / CS methods and preprints. Use for `method` and technical `adjacent` queries. Skip it for purely clinical queries.
   - `biorxiv` — bioRxiv **and** medRxiv preprints (one source name, both servers); use when recency matters or when the claim could be scooped by unpublished work.
   - `semanticscholar` — cross-cuts everything; a reasonable third source on most queries.
   - `openalex` — broadest coverage and concept-level indexing; best for `group` and `venue` axes and for anything non-English or outside the major indexes.
   - `crossref` — DOI/title-level metadata across publishers; best for `venue` queries, proceedings, book chapters, and journals the other indexes cover unevenly.

4. **Write plain keyword phrases, not query DSL.** 3-10 content words, no leading stopwords, no punctuation beyond hyphens. Do **not** emit Boolean operators, field tags, quotes, or wildcards (`AND`, `OR`, `[tiab]`, `"..."`, `*`) unless `sources` is exactly `["pubmed"]` or `["europepmc"]` — those two parse query syntax; the others receive the string as a bag of words, where an `AND` becomes a literal token. This is not a stylistic preference — it is measured. On arXiv, `free water diffusion MRI Alzheimer` returns diffusion-MRI papers, while `free water AND diffusion AND Alzheimer` returns *"Against free will in the contemporary natural sciences"* and *"What does a group algebra of a free group know about the group?"* — a full page of results, none of them related, and no error to signal it. The same string sent to PubMed works correctly. If you want a Boolean or field-tagged query, isolate it in its own entry with `sources` set to `["pubmed"]` or `["europepmc"]` alone.

5. **Vary specificity deliberately across the set.** Roughly: one third narrow (all four tuple elements present — these confirm or kill the claim outright), one third medium (two or three elements — these find the near misses), one third broad single-concept (these find the vocabulary you did not know to use). An all-narrow set returns nothing and reads as false reassurance of novelty; an all-broad set returns noise.

6. **Round > 1 must not repeat itself.** Every `query` string must be materially different from every entry in `already_tried` — not merely reordered, re-cased, or one stopword apart. Treat two queries as duplicates if they share the same content words. Additionally, on later rounds:
   - **Target the critic's gaps first.** Each item in `critic_hints` should map to at least one new query. If the critic says "nothing from the bi-tensor camp", the round-2 set must contain bi-tensor-vocabulary queries; if it says "all hits post-2020", add historical-vocabulary and `venue`-axis review queries that reach the back catalog.
   - **Rotate axes toward the ones that were underused.** If round 1 was method-heavy, weight round 2 toward `group`, `venue`, and `adjacent` — those are the axes that surface the literature a method-first search structurally cannot see.
   - **Escalate breadth as rounds go up.** Later rounds should be broader and stranger than earlier ones. By round 3 you should be querying adjacent diseases, adjacent modalities, and the method's pre-rename name.
   - Keep `synonyms` cumulative: re-emit prior aliases plus whatever new vocabulary the critic's hints or the round's framing implies.

7. **Cover `alt_framings` too, when the caller supplies them.** The broader framing and the sideways/adjacent framing from `novelty-frame.md` each deserve at least one query. The sideways framing is the highest-yield single query in the set — it is the one that finds the paper that scoops the claim from another field.

8. **Strict JSON only.** Emit exactly one JSON object with exactly the two top-level keys `queries` and `synonyms` — no prose before or after, no markdown fence, no trailing commas, no comments in the emitted output. Every `queries` entry has exactly the keys `axis`, `query`, `sources`. `axis` must be one of `method`, `task`, `data`, `outcome`, `group`, `venue`, `adjacent`. `sources` must be non-empty and drawn only from the seven names in Rule 3.

9. **Empty / failure case.** If `claim_tuple` is empty or unusable (all fields blank, or the upstream framing stage returned `skip: true`), return exactly:
   ```json
   {"queries": [], "synonyms": {}}
   ```
   Do not guess queries from a missing claim — an invented claim generates confidently on-topic searches for a question nobody asked, and the downstream synthesis will read as if the sweep was covered. An empty result is a clean no-op the caller handles; a fabricated one is not recoverable.
