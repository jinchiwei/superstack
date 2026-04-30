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

## state.json schema (v1)

See `DESIGN.md` for full schema. Phase transitions: `planning → running → (completed | halted | cancelled)`.

## Modes

- **INIT** — first invocation, no state.json. Plans axes, asks for confirmation, schedules iter 1.
- **RUNNING** — every subsequent invocation (fired by ScheduleWakeup). Runs one iteration, replans, schedules next.

## When research-log isn't set up

If `~/arcadia/research-log/` is absent or not a git repo, the skill falls back to a local `~/.gstack/projects/<slug>/autoresearch/notes.md`. Setup-agnostic.
