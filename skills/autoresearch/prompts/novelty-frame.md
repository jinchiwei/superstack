# Novelty framing prompt

You are bootstrapping an /autoresearch session. Before any literature search runs, convert the user's vague scope into a **precise, falsifiable claim** whose novelty can actually be checked against the literature.

The core teaching: *"is this novel?"* is unanswerable — there is no search that settles it. *"Has anyone predicted MGMT methylation status from MRI radiomics in primary CNS lymphoma?"* is answerable — a bounded set of searches either turns up such a paper or does not. Your job is to force the scope down to the second kind of question. Everything downstream (query expansion, the completeness critic, the novelty verdict) is only as good as the claim you write here.

**Inputs:**
- `scope`: free-text description of the experiment search space (e.g. "iterate over architectures, input modes, loss functions for the FW prediction model")
- `project_context`: a Read of the user's project README / CLAUDE.md / relevant code, if useful. May be empty.

**Output (JSON, no prose):**

```json
{
  "claim_tuple": {
    "method": "<the technique whose application is at stake — model family, algorithm, statistical design, imaging metric>",
    "task": "<the inference being made — prediction, classification, causal estimate, association test>",
    "data": "<the cohort / modality / dataset the claim is scoped to — disease, imaging modality, registry, sample size class>",
    "outcome": "<the measured endpoint — the label, biomarker, clinical event, or metric being produced>"
  },
  "novelty_claim": "<ONE sentence, falsifiable, of the form 'No prior work has <method> to <task> <outcome> in <data>.' A single paper must be able to refute it.>",
  "alt_framings": [
    "<same claim stated one notch broader — what a reviewer would say the contribution really is>",
    "<same claim stated one notch narrower — the defensible fallback if the broad claim is already taken>",
    "<a sideways framing: same method, adjacent disease/modality — where a scoop is most likely to be hiding>"
  ],
  "skip": false,
  "skip_reason": ""
}
```

**Rules:**

1. **Specificity is the whole product.** Every field of `claim_tuple` must be a named, searchable thing. Reject your own first draft if any field could describe fifty different papers.
   - Bad: `method: "deep learning"`, `task: "prediction"`, `data: "MRI"`, `outcome: "outcome"`
   - Good: `method: "handcrafted radiomics + gradient-boosted trees"`, `task: "preoperative binary classification"`, `data: "primary CNS lymphoma, 3T T1-post + FLAIR, single-center n<300"`, `outcome: "MGMT promoter methylation status"`
   - A field is too vague if you cannot imagine a keyword query that would return mostly on-target hits for it.

2. **`novelty_claim` must be falsifiable by a single paper.** Write it so that one PDF, if it exists, kills it. "Our approach is more principled" is not falsifiable. "No prior work has estimated free-water fraction from single-shell dMRI in NACC-scale cohorts and related it to tau PET" is. Prefer the negative-existential form ("No prior work has X"); it is the form the downstream searches are trying to break.

3. **The claim describes what is AT STAKE, not what is planned.** The user may be sweeping ten architectures. The novelty is not "we swept ten architectures" — it is whichever of {method, task, data, outcome} would be new if the sweep succeeds. Name that. If nothing in the tuple would be new and the contribution is empirical scale or replication, say so directly in `novelty_claim` ("Prior work has done X; the claim at stake is replication at N=1192 in an independent cohort"). An accurate weak claim beats an inflated one — the point is to tell the user what they are walking into before they burn hours.

4. **`alt_framings`: 2-4 entries, each a complete sentence, each materially different in scope.** Not paraphrases. The broader framing is what a skeptical reviewer will collapse the work into; the narrower one is the fallback that survives if the broad claim is already published; the sideways one is where an unnoticed scoop lives (same method in glioma instead of PCNSL; same task from CT instead of MRI). Downstream query expansion searches all of them, so a lazy `alt_framings` directly costs recall.

5. **Inherit the project's vocabulary.** If `project_context` names a cohort (ADNI, NACC, UNOS), a pipeline (FERNET, FreeSurfer), or a metric (free-water fraction, CDR-SB), use that exact term in `claim_tuple` — plus, where the term is house jargon, the field-standard synonym alongside it. Do not invent a cohort or metric the context does not support.

6. **Skip classification (carried over from `lit-review-classify.md`).** Set `skip: true` with a one-sentence `skip_reason` when the scope is not a research task:
   - QA / regression test automation across configurations
   - Build matrix exploration (e.g. "test under Python 3.10/3.11/3.12 × Linux/macOS")
   - Performance benchmarking of an internal product with no comparable academic literature
   - Configuration sweep purely for ops / deployment tuning
   - Anything where the user is iterating over an artifact they own end-to-end with no expectation of a publishable contribution
   - The scope is incoherent: uninterpretable, self-contradictory, or missing the context needed to name even one field of the tuple. Skip rather than guess — a fabricated claim poisons every downstream search.

7. **Permissive default (the 95% case).** When uncertain, set `skip: false` and frame the claim. Proceed for: model architecture / hyperparameter / loss / input-modality sweeps, algorithm comparison, biomedical and scientific experiments (datasets, statistical methods, biomarkers), and anything where similar work has plausibly been published.

8. **Skip output shape.** When `skip: true`, still emit the full object with empty placeholders, so consumers can parse one schema:
   ```json
   {
     "claim_tuple": {"method": "", "task": "", "data": "", "outcome": ""},
     "novelty_claim": "",
     "alt_framings": [],
     "skip": true,
     "skip_reason": "Build matrix exploration across Python versions; no comparable academic literature."
   }
   ```

9. **Strict JSON only.** Emit exactly one JSON object and nothing else — no prose before or after, no markdown fence, no trailing commas, no comments. All five top-level keys are always present. `skip_reason` is `""` when `skip` is `false`. Never emit `null` for a string field; use `""`.

10. **Length budget.** Each `claim_tuple` field ≤ 20 words, `novelty_claim` ≤ 40 words, each `alt_framings` entry ≤ 30 words. This object is quoted verbatim into the user's confirmation prompt and into every downstream query-expansion call — it has to stay small enough to repeat cheaply.
