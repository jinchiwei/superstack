---
name: pipeline
description: Use when starting a new project from scratch or when the user says "pipeline" — walks the full ideation-to-ship-to-reflect workflow step by step, choosing the right gstack / superpowers / superstack skill at each stage
---

# Project Pipeline (v2 — Sep 2026)

End-to-end workflow: **Ground → Think → Design → Plan → Build → Review → Test → Ship → Reflect**.
Each stage names its skill and the condition under which it runs. Conditional stages are skipped
with a one-line reason, never silently.

## The Pipeline

```
GROUND (research-flavored projects only)
  0a. autoresearch lit review     Recall-first literature sweep + adversarial novelty check
                                   (7 sources incl. OpenAlex snowballing). Run when the project
                                   makes a scientific or "nobody has done X" claim.
  0b. /deep-research               Market / landscape / prior-art sweep with verified claims.
                                   Run when positioning against competitors or existing tools.

THINK
  1.  /office-hours  OR  /spec     office-hours when intent is vague or ambitious (six forcing
                                   questions -> design doc). /spec when intent is already clear
                                   (five phases -> filed issue + executable spec). Never both.

DESIGN (UI projects only)
  2a. /design-consultation         Greenfield: proposes the whole design system -> DESIGN.md
  2b. /design-shotgun              Explore 4-6 mockup variants, pick with taste memory
  2c. /design-html                 Turn the approved mockup into production HTML/CSS

PLAN
  3.  /writing-plans               Implementation plan: 2-5 min tasks, exact paths, complete code
  4.  /autoplan                    Batched review: CEO -> design -> DX -> eng (eng last) + codex.
                                   Surfaces only taste calls. Manual fallback: /plan-ceo-review,
                                   /plan-design-review, /plan-devex-review, /plan-eng-review,
                                   /codex consult.

BUILD
  5.  /guard <project-dir>         Scope edits + destructive-command warnings
  6.  /subagent-driven-development Per task: /test-driven-development,
                                   /verification-before-completion
  7.  /verify                      Drive the real app end to end; observe the change working
  7b. /simplify                    Optional: reuse / altitude / efficiency pass on the diff

REVIEW
  8.  /review                      Staff-engineer diff review (fix-first)
  9.  /codex review                Independent cross-model review, pass/fail gate
  10. /health                      Optional: type + lint + tests + dead code composite score
  11. /cso                         Security. REQUIRED for auth, secrets, PII, network input,
                                   file/path handling, SQL, shared infra, LLM trust boundaries.

TEST (by audience)
  12. end users  -> /qa  then /design-review        (optional /benchmark for perf baselines)
      developers -> /devex-review                   (docs, CLI, SDK, onboarding TTHW)

SHIP
  13. /ship                        Version bump, changelog, PR
  14. /land-and-deploy             Merge, wait for CI + deploy, verify prod   (needs /setup-deploy once)
  15. /canary                      Post-deploy monitoring (background)
  16. /document-release            Sync docs to what shipped (calls /document-generate for gaps)
  17. /unfreeze                    Release the /guard scope

REFLECT
  18. /learn  +  record_learning   gstack learnings + the vault kb (constraints / decisions /
                                   postmortems / results). Non-optional: this is what compounds.
  19. /retro                       Weekly; not per-project
  20. Communicate (research work)  /build-pptx (autoresearch-style deck), /build-pdf, /paper-outline

ANY TIME
  * /investigate                   Root-cause first on any failure before retrying the step
  * /context-save                  Before a long pause; /context-restore to resume
```

## Pre-Flight Check

Before Step 0, check that the tooling is fresh. Works on Linux and macOS:

```bash
for repo in ~/arcadia/superstack/.upstream/superpowers ~/.claude/skills/gstack; do
  f="$repo/.git/FETCH_HEAD"; [ -f "$f" ] || continue
  last=$(stat -c %Y "$f" 2>/dev/null || stat -f %m "$f" 2>/dev/null || echo 0)
  days=$(( ( $(date +%s) - last ) / 86400 ))
  [ "$days" -gt 14 ] && echo "STALE: $(basename "$repo") last pulled ${days}d ago"
done
```

If anything is STALE, offer `/pipeline-update` (superpowers + gstack + superstack skills in one
pass). If the user declines, continue.

## How to Run

Go step by step. For each step:
1. Say which step you are on and what it does (one sentence).
2. Invoke the skill.
3. When it completes, confirm before moving on — unless the user has said "autoresearch style"
   or "run it through", in which case proceed autonomously and stop only at the gates marked
   below (plan approval, ship, land).

## Stage Notes

### Ground (0a, 0b) — research-flavored projects
Jinchi's projects usually carry a scientific claim. Run the autoresearch Step 2.5 engine
(`bin/lit-search --source all`, `bin/lit_snowball.py`, the four-lens novelty panel) BEFORE
office-hours so the framing conversation starts from what already exists. Output lands in a
`lit/` directory the deck and paper can cite later. Skip for pure tooling / ops projects.

### Think (1) — office-hours vs spec
Decision rule: if you can already write the one-sentence deliverable and name the files it
touches, use `/spec` (it files the issue and can spawn a worktree agent). If you cannot, use
`/office-hours`. Running both is redundant; office-hours' design doc IS the input to
`/writing-plans`, and `/spec`'s spec IS too.

### Design (2a-2c) — UI projects only
`/design-consultation` only when there is no DESIGN.md. `/design-shotgun` when the user wants to
see options; skip when the direction is already settled. `/design-html` is optional — use it
when the plan will otherwise start from a blank page. Ask about UI here so Test knows whether
`/qa` and `/design-review` apply.

### Plan (3, 4)
Always write the plan, even if the user says "just build it": plan quality is what makes the
autonomous build phase work. `/autoplan` already runs DX review — do not add
`/plan-devex-review` on top of it. **GATE: the user approves the reviewed plan before Build.**

### Build (5-7b)
`/guard` first; widen deliberately (`/unfreeze` then re-`/guard`) if the project spans dirs.
`/verify` after the build is not optional for anything with a runtime surface: tests passing
is not the same as the change working. `/simplify` is a quality pass, not a bug hunt.

### Review (8-11)
`/review` and `/codex review` are complementary; agreement between them is only ~30%, so one
alone misses a lot. Builtin `/code-review` overlaps `/review` — pick one, default `/review`.
`/security-review` (builtin, diff-scoped) is an alternative to `/cso` daily mode for small
diffs; `/cso` for anything infra-touching.

### Test (12) — pick by audience
| Building for | Live audit |
|---|---|
| End users (UI, web, mobile) | `/qa` -> `/design-review` (+ `/benchmark` for perf) |
| Developers (API, CLI, SDK, docs) | `/devex-review` |
| iOS on device | `/ios-qa` -> `/ios-fix` -> `/ios-design-review` |

### Ship (13-17)
`/ship` opens the PR. **GATE: user confirms before `/land-and-deploy`** — landing is
outward-facing. `/canary` runs in the background while docs update. `/document-release` will
call `/document-generate` for anything the Diataxis coverage map shows missing.

### Reflect (18-20)
`/learn` + `record_learning` are the compounding step: constraints hit, decisions made, dead
ends ruled out, results worth not rediscovering. `/retro` is weekly cadence, not per-project.
For research work the last deliverable is the communication artifact — an autoresearch-style
`/build-pptx` deck (bespoke figures, lit-positioning grid, data-and-processing slide) and/or
`/build-pdf`.

## Abbreviated Pipelines

**Minimal (side project, CLI tool, no UI, no deploy):**
```
/spec -> /writing-plans -> /plan-eng-review -> /subagent-driven-development -> /verify -> /ship -> /learn
```

**Standard (most projects with deploy):**
```
/office-hours -> /writing-plans -> /autoplan -> /guard -> /subagent-driven-development -> /verify
  -> /review -> /codex review -> /ship -> /land-and-deploy -> /canary -> /unfreeze -> /learn
```

**Research (claims a scientific result; Jinchi's default):**
```
autoresearch lit review -> /office-hours -> /writing-plans -> /autoplan -> /guard
  -> /subagent-driven-development -> /verify -> /review -> /codex review -> /ship
  -> record_learning -> /build-pptx
```

**Full (ambitious project with UI):** all stages 0-20, with 2a-2c as applicable.

## Removed from v1, and why

- `/plan-devex-review` as a separate step: `/autoplan` already runs it.
- `/checkpoint`: renamed upstream to `/context-save`.
- `/make-pdf` as the default PDF path: `/build-pdf` is the branded default here; `/make-pdf`
  only for neutral, unbranded output.
- Separate 3a-3d enumeration as the primary path: it is now the manual fallback under `/autoplan`.
- BSD-only `stat -f %m` in pre-flight: silently failed on Linux, so staleness was never detected.

## Rules

- Never skip a step silently. Say why, then skip.
- Never start Build without an approved reviewed plan.
- Never `/land-and-deploy` without the user's explicit go: it is outward-facing.
- Ask about UI at Plan time so Test is scoped correctly.
- On any failure, `/investigate` before retrying. Treat the failure as a symptom.
- `/guard` scope is session-wide; widen deliberately, not by editing around it.
- Steps 10 (`/health`) and 11 (`/cso`) default on; skip only with a one-line reason.
- Step 18 (Reflect) is not optional. A pipeline that does not record what it learned will
  rediscover it next time.
