# Axis enumeration prompt

You are bootstrapping an /autoresearch session. The user gave you a free-text scope describing what to explore. Convert it into a concrete experiment search space.

**Inputs:**
- `scope`: free-text description (e.g. "iterate over architectures, input modes, loss functions for the FW prediction model")
- `project_context`: a Read of the user's project README/CLAUDE.md/relevant code if useful
- `lit_review_summary` (optional): the `axis_implications` field from the upstream Step 2.5 lit-review synthesis. Empty string means no lit context (either it was skipped, the search returned nothing relevant, or lit review failed). When non-empty, it names specific axis values the literature suggests including or excluding (e.g. "transformers consistently outperform CNNs on this task; consider adding a transformer baseline").

**Outputs (JSON, no prose):**

```json
{
  "scope_slug": "<2-3 hyphenated words capturing the search domain>",
  "target_metric": {"name": "<metric>", "op": ">|<|>=|<=|=", "threshold": <number>} or null if user did not specify,
  "axes": {
    "<category1>": ["<value1>", "<value2>", ...],
    "<category2>": ["<value1>", ...]
  },
  "target_axis": "<axis-key-name>" | ["<axis-key-1>", "<axis-key-2>"] | null,
  "rationale": "<1-2 sentences on why these axes were chosen>"
}
```

**Rules:**
1. Each axis is a category with 2-8 concrete options. Don't enumerate continuous ranges as discrete values unless the user named them.
2. Stick close to what the scope says. Don't invent unrelated dimensions.
2a. **Honor `lit_review_summary` when present.** If the lit review explicitly suggests including a specific approach as a baseline ("consider adding a transformer baseline"), include it as an axis value when it fits the scope. If the lit review identifies a specific approach that's been shown not to work in this domain ("plain MLPs collapse on this task"), omit that value. The summary is advisory, not commanding — if the user's scope explicitly contradicts the lit review's suggestion (e.g., scope says "MLPs only"), follow the scope. Note any such overrides in `rationale`.
3. If the user named a target metric in the scope ("until val_corr > 0.85"), parse it. If not, set target_metric to null and rely on exhaustion-stop.
4. scope_slug is filename-safe (lowercase, hyphens, no special chars). Should make sense as a research-log entry slug.
5. If you can't make sense of the scope, return `{"error": "<one-sentence reason>"}` instead — the SKILL.md handles the error path.
6. **Axis order = chronological sweep order.** List axes in the order they would naturally be swept first → last (e.g., backbone before regularization, model before input modality before evaluation strategy). The downstream `_build_xlsx.py` Axis Matrix renders sections top-to-bottom in this order, so the spreadsheet reads as the actual research journey. If a target axis exists (see Rule 7), it goes LAST in the dict — it's rendered as columns rather than rows, but ordering still matters for iteration loops.

7. **Target axis declaration.** Many projects sweep across a set of prediction targets in addition to hyperparameters — genes (radiogenomics), pathogens (CurieDx: flu, covid, strep, RSV), tasks (multi-task NLP), languages, datasets. If the scope implies one of these, include it as a normal axis AND set `target_axis` to that axis's key name. Examples:
   - CurieDx: `axes.pathogen = ["flu", "covid", "strep"]`, `target_axis = "pathogen"`
   - Radiogenomics: `axes.gene = ["TP53", "ATRX", ...]`, `target_axis = "gene"`
   - Multi-task NLP: `axes.task = ["sentiment", "ner", "qa"]`, `target_axis = "task"`

   The Axis Matrix renders the target axis as side-by-side **columns** (one per target value) so per-target winners can be scanned at a glance. Hyperparameter axes become row sections. If there is no natural target axis (a single-target sweep), set `target_axis: null` and the matrix renders a single "Best metric" column.

   **Multiple target axes.** When the scope has more than one orthogonal target dimension (e.g., a CurieDx sweep across both `pathogen` AND `tissue` = nasal/throat swab; a multi-modal radiogenomics sweep across `gene` AND `modality` = MRI/CT), set `target_axis` to a **list** of axis keys: `target_axis = ["pathogen", "tissue"]`. The xlsx builder will produce one Axis Matrix sheet per target axis, each treating that axis as columns and the rest (including other target axes) as row sections — a marginal view. Don't list more than 2 target axes; beyond that it's likely a misclassification of the search space.

**Cardinality budget:**
The full Cartesian product of axes is the worst-case search space. Keep it under ~50 cells unless the scope explicitly asks for exhaustive sweep. If the product would exceed 50, propose smaller axis vocabularies.

**Output-path convention:**
The autoresearch skill organizes outputs as:
- `results/<YYYYMMDD>_<scope_slug>/iter-<NN>_<candidate-slug>/` — synthesized outputs (figures, summary.md, csv) — committed
- `exp/<YYYYMMDD>_<scope_slug>/iter-<NN>_<candidate-slug>/` — raw artifacts (checkpoints, large logs) — gitignored

When you write the per-iteration experiment command in SKILL.md Step 3, your candidate scripts MUST honor two env vars exported by the skill:
- `$AUTORESEARCH_OUT_RESULTS` — the results dir for this iteration (always exists when the script runs)
- `$AUTORESEARCH_OUT_EXP` — the exp dir for this iteration (always exists)

Each iteration MUST write a `summary.md` into `$AUTORESEARCH_OUT_RESULTS/summary.md` so downstream report builders can find it.
