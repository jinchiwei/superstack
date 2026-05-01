# superstack

Blends complementary skills from [superpowers](https://github.com/obra/superpowers) and [gstack](https://github.com/garrytan/gstack) into a single pipeline for Claude Code and OpenAI Codex with minimal overhead.

## Claude Setup

```bash
git clone git@github.com:jinchiwei/superstack.git ~/arcadia/superstack
cd ~/arcadia/superstack
./setup
```

Requires [bun](https://bun.sh) (for gstack's browser build).

Running `./setup` again is safe -- it skips work when everything is already up to date.

## Codex Setup

Install the Codex version of the same pipeline:

```bash
cd ~/arcadia/superstack
./install-codex
```

This command:

- runs `./setup` so the gstack and superpowers sources are present
- refreshes the four Superpowers-derived Codex overlays from upstream `superpowers/skills`
- runs gstack's `./setup --host codex` to generate `~/.codex/skills/gstack-*` when the generated skills are missing or stale
- compacts generated gstack skill descriptions to avoid Codex skill-budget warnings
- installs the Codex overlays from `codex-skills/` into `~/.codex/skills`

The Codex overlays include `$pipeline`, `$writing-plans`, `$subagent-driven-development`,
`$test-driven-development`, `$verification-before-completion`, `$pipeline-update`,
`$pipeline-update_codex`, and `$claude`.

Reruns are idempotent: if gstack and the generated Codex skills are current, dependency-heavy
generation is skipped. Use `./install-codex --force-gstack-codex` to force regeneration, or
`./install-codex --no-compact-descriptions` to leave generated descriptions untouched.

## Update

Pull latest from upstream sources:

```bash
./update
./install-codex  # if you also use Codex
```

Or from Claude Code:

```
/pipeline-update
```

## What gets installed

| Source | Skills |
|--------|--------|
| **gstack** | browse, qa, ship, design-\*, plan-\*, review, office-hours, and [more](https://github.com/garrytan/gstack) |
| **superpowers** | subagent-driven-development, test-driven-development, verification-before-completion, writing-plans |
| **this repo** | pipeline, pipeline-update, autoresearch |
| **this repo, Codex only** | claude second-opinion skill |

## The pipeline

```
THINK
  1. /office-hours              Clarify what to build
  2. /writing-plans             Write the implementation plan
  3. /autoplan                  Batched plan review (CEO + design + eng + DX + codex)
                                Fast path — auto-decides; surfaces close calls at a gate.
                                Manual fallback: /plan-ceo-review, /plan-design-review,
                                /plan-eng-review, /codex consult

BUILD
  4. /guard <project-dir>       Scope edits + destructive-command warnings
  5. /subagent-driven-development
     (each subagent uses /test-driven-development + /verification-before-completion)

VERIFY + SHIP
  6. /review                    Pre-landing code review
  7. /codex review              Cross-model diff review (independent model)
  8. /qa + /design-review       (if UI) Test and polish
  9. /ship                      Version bump, changelog, PR
  10. /document-release         Sync docs to what shipped
  11. /unfreeze                 Release the guard scope

If a step fails or you hit a bug mid-pipeline:
  * /investigate                Root-cause-first debugging before retrying
```

For Codex, the equivalent pipeline uses `$gstack-*` skills and replaces the old
Claude-side `/codex review` step with `$claude review`, which calls Claude Code with
xhigh effort for an outside-model pass.

## /autoresearch

Long-running autonomous research loop. Use when you want to iterate over a search space
(architectures, input modes, hyperparameters, etc.) for hours-to-days, with adaptive
replanning, agentic code-fix on failures, and a STOP-file kill switch. One invocation
per session — the skill self-paces via `ScheduleWakeup` and runs without prompts after
launch.

```
/autoresearch "iterate over architectures, input modes, loss functions for the FW model.
                target: val_corr > 0.85"
```

You'll be asked once at launch to confirm the planned axes. After that:

- **One iteration per ScheduleWakeup tick** — pick next candidate, run the experiment,
  classify any failure (transient / code_bug / infrastructure / unknown), replan the
  queue, append to the live narrative, schedule the next iteration.
- **State persisted** at `~/.gstack/projects/<slug>/autoresearch/state.json` so a Claude
  Code crash mid-session is recoverable (run `/autoresearch` with no args to resume).
- **Stop signals** — target metric reached, search space exhausted, `touch STOP` file,
  or 2 consecutive distinct infrastructure failures (D4 halt gate).
- **Standardized outputs** per iteration:
  - `results/<YYYY-MM-DD>_<scope>/iter-<NN>_<candidate>/` — synthesized (figures,
    metrics, `summary.md`); committed
  - `exp/<YYYY-MM-DD>_<scope>/iter-<NN>_<candidate>/` — raw artifacts (checkpoints,
    big logs); gitignored
  - Candidate scripts honor `$AUTORESEARCH_OUT_RESULTS` and `$AUTORESEARCH_OUT_EXP`
    (exported by the skill; no hardcoded paths).
- **Brand-styled session reports** at termination — runs any of
  `docs/_build_pptx.py`, `docs/_build_docx.py`, `docs/_build_pdf.py` that exist with
  `--date <date> --scope <slug>`. Templates dropped by `init-project` use Geist + the
  brand palette (turquoise / deeppink / amber / blueviolet) and produce a
  conference-presentation-quality deck plus conservative paper-style docx/pdf.

See `skills/autoresearch/USAGE.md` for full invocation, halt, and inspection patterns,
and `skills/autoresearch/DESIGN.md` for the architecture (locked decisions D1-D4 on
stash discipline, iteration error wrapping, schema migration, and infra halt gating).
