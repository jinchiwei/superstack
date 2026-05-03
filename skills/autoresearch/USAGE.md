# /autoresearch USAGE

## Invoke

```
/autoresearch "<free-text scope>"
```

The scope text should describe what to explore and (optionally) when to stop. Examples:

- `/autoresearch "iterate over architectures, input modes, loss functions for the FW model. target: val_corr > 0.85"`
- `/autoresearch "sweep learning rate × batch size × optimizer for the small classifier"`
- `/autoresearch "try data augmentations and dropout values to reduce overfitting on val_loss"`

You'll be asked ONCE at launch to confirm the planned axes. Choose:

- **Confirm and launch** — start the loop
- **Edit axes** — redirect via free-text
- **Cancel** — exit without writing state

After launch, the loop self-paces and runs without prompts.

## Halt

```bash
touch ~/.gstack/projects/<slug>/autoresearch/STOP
```

The skill checks for this file at the start of each iteration. It finishes the in-flight iteration cleanly, writes a final summary, and exits.

## Resume after a Claude Code crash

State is persisted at `~/.gstack/projects/<slug>/autoresearch/state.json`. To resume:

```
/autoresearch
```

(no args) — picks up from existing state.json.

## Inspect

- State: `~/.gstack/projects/<slug>/autoresearch/state.json`
- Last iteration log: `~/.gstack/projects/<slug>/autoresearch/last-iteration.log`
- Deferred questions: `~/.gstack/projects/<slug>/autoresearch/QUESTIONS_FOR_USER.md`
- Live narrative: research-log entry (if set up) or local `notes.md`

## Project layout

The skill writes per-iteration outputs into a date+scope+candidate hierarchy in your project root, mirroring the convention used in `brainlab/projects/ad/agf/ad-genetics-fwf/`:

```
<project>/
  exp/                                          (gitignored, raw artifacts)
    YYYY-MM-DD_<scope>/
      iter-NN_<candidate>/                      checkpoints, big logs
  results/                                      (committed, synthesized)
    YYYY-MM-DD_<scope>/
      README.md                                 session dashboard (axes, metrics table)
      iter-NN_<candidate>/
        summary.md                              required: per-iter blurb
        figures/, *.csv, etc.
  docs/
    _build_pptx.py / _build_docx.py / _build_pdf.py   templates dropped by init-project
    runs/
      YYYY-MM-DD_<scope>/SESSION_REPORT.{pptx,docx,pdf}   produced at termination
```

Each iteration's command receives two env vars from the skill:
- `$AUTORESEARCH_OUT_RESULTS` — absolute or repo-relative path to that iteration's results dir
- `$AUTORESEARCH_OUT_EXP` — same for exp/

Scripts in your candidate command MUST honor these (write `summary.md`, figures, etc. into `$AUTORESEARCH_OUT_RESULTS`; checkpoints into `$AUTORESEARCH_OUT_EXP`). The skill bootstraps the layout via `bin/init-project` on first run; safe to re-run.

## Session reports

At termination, the skill invokes any of `docs/_build_pptx.py`, `docs/_build_docx.py`, `docs/_build_pdf.py` that exist, calling each with `--date <date> --scope <scope>`. Templates dropped by `init-project` use the standard brand palette (turquoise / deeppink / amber / blueviolet, Geist + Geist Mono) and read `results/<date>_<scope>/` plus per-iteration `summary.md`. Edit the templates to fit your project; the contract is the CLI args plus the input/output paths.

Report builds are best-effort: failures (missing `python-pptx` etc.) are logged but don't block termination.

Pip prereqs:
- `pip install python-pptx python-docx markdown weasyprint openpyxl`
- macOS PDF builder also needs system libs: `brew install pango glib`

## state.json schema (v1)

See `DESIGN.md` for full schema. Phase transitions: `planning → running → (completed | halted | cancelled)`.

## Modes

- **INIT** — first invocation, no state.json. Plans axes, asks for confirmation, schedules iter 1.
- **RUNNING** — every subsequent invocation (fired by ScheduleWakeup). Runs one iteration, replans, schedules next.

## Gotchas

- **commit-experiment uses `git add -A`.** Each successful iteration stages everything in the project repo and commits it. If you have uncommitted unrelated work in the project repo when /autoresearch runs, that work will be bundled into the first iteration commit. Start /autoresearch with a clean (or intentionally staged) working tree.
- **/autoresearch mutates your working tree on code-fix attempts.** During a `code_bug` failure, the skill stashes your tree, applies an LLM-proposed Edit on a clean tree, reruns, and either: (a) on success — commits the fix and `git stash pop`s your prior work back into the tree (you may see uncommitted state on top of the fix commit; the next `commit-experiment` sweeps it via `git add -A`); or (b) on failure — reverts via `git checkout -- <fix_target>` + `git stash pop`. Mid-fix interruption is recoverable via the `pending_stash_ref` field in state.json.
- **Stash-pop conflicts on success path.** If your pre-existing uncommitted work touches the same lines as the LLM's fix, `git stash pop` after the success commit will leave conflict markers in the file. The stash is preserved (not dropped), so no data loss; you'll resolve the conflict on return.
- **Single /autoresearch session per project.** Two concurrent sessions on the same project would race on state.json and on research-log appends. Not enforced; just avoid.

## When research-log isn't set up

If `~/arcadia/research-log/` is absent or not a git repo, the skill falls back to a local `~/.gstack/projects/<slug>/autoresearch/notes.md`. Setup-agnostic.
