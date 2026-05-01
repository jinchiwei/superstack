---
name: pipeline
description: Use when starting a new project from scratch or when the user says "pipeline" — walks through the full ideation-to-ship workflow step by step
---

# Project Pipeline

Full project workflow from idea to shipped code. Follow each step in order. Skip steps only when the user explicitly says to.

## The Pipeline

```
THINK ──────────────────────────────────────────────────────
  0. /design-consultation  Greenfield UI projects only — produces DESIGN.md
                           (aesthetic, typography, color, layout, motion).
                           Skip for non-UI projects, or if a DESIGN.md
                           already exists.
  1. /office-hours         Clarify what to build
  2. /writing-plans        Write the implementation plan
  3. /autoplan             Batched plan review (CEO + design + eng + DX + codex)
                           Fast path — auto-decides; surfaces close calls at a gate.

                           Manual path (offer if user wants granular control):
                             3a. /plan-ceo-review    If scope/ambition is uncertain
                             3b. /plan-design-review If the project has UI
                             3c. /plan-eng-review    Lock architecture + test plan
                             3d. /codex consult      Adversarial second opinion on the plan

BUILD ──────────────────────────────────────────────────────
  4. /guard <project-dir>  Scope edits + destructive-command warnings
  5. /subagent-driven-development
     Each subagent uses:
       - /test-driven-development (TDD per task)
       - /verification-before-completion (evidence before claims)

VERIFY ─────────────────────────────────────────────────────
  6. /review               Pre-landing code review
  7. /codex review         Cross-model diff review (independent model, catches what /review misses)
  8. /health               Code quality dashboard (type check + lint + tests + dead code)
                           Optional but cheap — flags rot before /ship.
  9. /cso (or /security-review)
                           Security audit. /cso daily mode = 8/10 confidence gate,
                           low noise. Always run for code touching auth, secrets, PII,
                           external network input, or shared infrastructure.
  10. /qa                  If it has UI — test and fix bugs
      /design-review       If it has UI — visual polish

SHIP ───────────────────────────────────────────────────────
  11. /ship                Version bump, changelog, PR
  12. /land-and-deploy     Merge the PR, wait for CI + deploy, verify production health
  13. /canary              Post-deploy monitoring — console errors, perf regressions,
                           page failures. Establishes / refreshes baselines.
  14. /document-release    Sync docs to what shipped
  15. /unfreeze            Release the guard scope

If a step fails or you hit a bug mid-pipeline:
  * /investigate           Root-cause-first debugging before retrying the step
```

## Pre-Flight Check

Before starting the pipeline, check if skills are stale:

```bash
# Check superpowers freshness (days since last pull)
if [ -d ~/arcadia/repos/superpowers/.git ]; then
    LAST_PULL=$(stat -f %m ~/arcadia/repos/superpowers/.git/FETCH_HEAD 2>/dev/null || echo 0)
    NOW=$(date +%s)
    DAYS_AGO=$(( (NOW - LAST_PULL) / 86400 ))
    if [ "$DAYS_AGO" -gt 7 ]; then
        echo "SUPERPOWERS_STALE ${DAYS_AGO}d"
    fi
fi
```

If `SUPERPOWERS_STALE` is detected, tell the user: "Your pipeline skills haven't been updated in X days. Want me to run `/pipeline-update` first?" If they say yes, invoke `/pipeline-update` before proceeding. If they decline, continue.

## How to Run

Work through the pipeline one step at a time. At each step:

1. Tell the user which step you're on and what it does (one sentence)
2. Invoke the skill
3. When that skill completes, ask: "Ready for the next step?" before moving on

## Step Details

### Step 0: Design Consultation (greenfield UI only)
If the project has UI AND there's no existing DESIGN.md, ask the user if they want to run `/design-consultation`. This proposes a complete design system (aesthetic, typography, color, layout, spacing, motion) and produces font + color preview pages. The resulting DESIGN.md becomes the source of truth for downstream steps. Skip for CLI tools, libraries, backend services, or any project that already has a design system.

### Step 1: Office Hours
Invoke `/office-hours`. This produces a design doc. Do not proceed until the user is satisfied with the design.

### Step 2: Writing Plans
Invoke `/writing-plans`. Use the design doc from Step 1 as input. This produces an implementation plan with 2-5 minute tasks, complete code, and exact file paths.

### Step 3: Plan Review
Ask the user which path they want:
- **Fast (recommended)**: `/autoplan` — batches CEO + design + eng + DX reviews with auto-decisions using 6 decision principles, surfaces only taste calls and codex disagreements at a final gate. One command, much less friction.
- **Manual**: offer the individual reviews so the user can redirect mid-flight:
  - `/plan-ceo-review` if scope/ambition is uncertain
  - `/plan-design-review` if the project has UI
  - `/plan-eng-review` to lock architecture + test coverage
  - `/codex consult` for an adversarial second opinion from an independent model

Always ask about UI at this step so you know whether `/qa` and `/design-review` are needed later.

### Step 4: Guard
Invoke `/guard` with the project directory to scope all edits to that path and warn before destructive commands. This is a safety rail for the autonomous build phase — a misfiring subagent can't clobber files outside the project. Use the project's parent dir if the project spans multiple folders.

### Step 5: Build
Invoke `/subagent-driven-development` with the reviewed plan. Each subagent should follow `/test-driven-development` and `/verification-before-completion`.

This is the autonomous execution phase. It may run for a while.

### Step 6: Review
Invoke `/review` to review the full diff before shipping. Checks SQL safety, LLM trust boundaries, conditional side effects, and structural issues.

### Step 7: Codex Review
Invoke `/codex review` for an independent diff review from an outside model (OpenAI Codex). This is cross-model validation — different models flag different classes of issue. The gstack v1.5.1 release notes document a ~30% agreement rate between Claude review and Codex, meaning one reviewer alone misses a lot.

Pass/fail gate. If Codex flags blockers, fix them before shipping.

### Step 8: Health (optional)
Invoke `/health`. Wraps the project's existing tools — type checker, linter, test runner, dead-code detector, shell linter — and computes a weighted composite 0–10 score. Tracks trends across runs. Cheap, fast, surfaces rot that diff-only review can't catch (dead code, type drift, lint regressions).

Skip on tiny patches with no test or lint surface.

### Step 9: Security Review (optional but defaulted-on for sensitive code)
For most diffs, invoke `/cso` in **daily mode** — infrastructure-first audit (secrets, dependency supply chain, CI/CD, plus OWASP Top 10 / STRIDE). Daily mode runs at an 8/10 confidence gate with zero-noise output, so most clean diffs pass quietly.

For tighter, change-scoped review, `/security-review` is an alternative — it focuses on the pending diff specifically.

ALWAYS run a security pass for diffs that touch: authentication, authorization, secrets/credentials, PII, external network input, file/path handling with user input, SQL/query construction, shared infrastructure, or LLM trust boundaries. For pure UI/refactor/docs changes, you can skip with a note.

### Step 10: QA (if UI)
If the project has UI, ask the user if they want to run `/qa` and/or `/design-review`.

### Step 11: Ship
Invoke `/ship` to version bump, generate changelog, commit, push, and create a PR.

### Step 12: Land + Deploy
Invoke `/land-and-deploy`. Merges the PR, waits for CI to pass and the deploy to complete, then runs canary health checks against production. This is the natural completion of `/ship` — without it, the pipeline ends at "PR open" and the user has to land + verify by hand.

If `/setup-deploy` hasn't been run for this project, `/land-and-deploy` will prompt for the deploy platform (Fly / Render / Vercel / Netlify / Heroku / GitHub Actions / custom), production URL, and health check endpoint, and persist them to CLAUDE.md so subsequent runs are zero-friction.

### Step 13: Canary
Invoke `/canary` to start post-deploy monitoring. Watches the live app for console errors, performance regressions, and page failures via the browse daemon. Establishes baselines if none exist; compares against pre-deploy baselines if they do. Especially valuable in the first 15–30 minutes post-deploy when most regressions surface. Can run in the background while you do Steps 14–15.

### Step 14: Document Release
Invoke `/document-release` to update docs to match what shipped (README, ARCHITECTURE, CONTRIBUTING, CLAUDE.md, CHANGELOG voice, TODOS, optional VERSION bump).

### Step 15: Unfreeze
Invoke `/unfreeze` to release the `/guard` edit-scope restriction set in Step 4. This ends the safety session — subsequent work can edit anywhere.

## Abbreviated Pipelines

If the user wants to move fast, suggest these shorter versions:

**Minimal (side project, CLI tool, no UI, no deploy):**
```
/office-hours → /writing-plans → /plan-eng-review → /subagent-driven-development → /ship
```

**Standard (most projects with deploy):**
```
/office-hours → /writing-plans → /autoplan → /guard → /subagent-driven-development
  → /review → /codex review → /ship → /land-and-deploy → /canary → /unfreeze
```

**Full (ambitious project with UI):**
All 15 steps (0 through 15), with `/design-consultation` if greenfield.

## Rules

- Never skip a step silently. If you think a step should be skipped, say why and ask.
- Never start building (Step 5) without a reviewed plan.
- Always ask about UI at Step 3 to determine whether design review and QA are needed later.
- If the user says "just build it" after Step 1, still run Step 2 (writing-plans) — the plan quality directly affects autonomous execution quality.
- If any step fails or surfaces unexpected behavior, invoke `/investigate` before retrying — treat the failure as a symptom and find the root cause first, don't paper over it.
- `/guard` scope is session-wide. Don't try to edit outside the scoped dir mid-pipeline; if the project needs it, widen the scope deliberately via `/unfreeze` → re-`/guard` the wider path.
- Steps 8 (`/health`) and 9 (`/cso`) are optional but defaulted-on. Skip explicitly with a one-line reason — don't quietly drop them on diffs where they'd add value.
- For code that touches auth, secrets, PII, or shared infrastructure, Step 9 (`/cso` or `/security-review`) is REQUIRED, not optional.
