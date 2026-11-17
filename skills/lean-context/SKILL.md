---
name: lean-context
description: >-
  Practices for keeping the context window lean while working. Apply at the START
  of any task that involves exploring, understanding, editing, or debugging a
  codebase, and BEFORE reading files or running commands that dump large output.
  Scout with search instead of reading whole files, delegate broad multi-file
  exploration to subagents, read only the slices you need, never re-read what's
  already in context, filter command output, offload intermediates to the
  filesystem, and hand off to a new session with a written handoff.
---

# Lean context

Every files, commands etc you pull in stays in the window, dilutes attention,
and buries the few lines that actually matter.
The goal is to hold the **minimum needed to act correctly**, not everything that
might be relevant. Optimize for signal, not coverage.

## Scout, then read the slice

Don't read whole files or directories to "get oriented." Locate first, then read
only the relevant span:

- `grep`/Glob to find the symbol, definition, or call site; then Read with
  `offset`/`limit` around it.
- Read a function or section, not the 800-line file, when you know what you need.
- Skim structure (signatures, a grep of function names) before committing to a
  full read.

## Delegate broad exploration to a subagent

When answering means sweeping many files ("how does X work?", "where is Y
handled?", naming conventions across the tree), spawn an Explore or
general-purpose subagent. It reads the files in its own context and returns just
the **conclusion** — the file dumps never touch your window. This is the single
biggest lever for keeping the main thread lean; use it liberally for
open-ended searches, and keep only the summary.

Brief it with paths, not pasted content, and say how long an answer you want. A
read-only search can run on a cheaper model.

## Don't re-read or re-run

Don't re-open files already in context, don't re-run a search whose answer you
already have, and don't re-run a command (tests, lint, a build) on code that
hasn't changed since it last ran.

## Filter output; never dump

A command's full output is rarely the thing you need:

- Pipe through `grep`/`head`/`tail`/field-selection; ask for the specific line,
  count, or status — not the whole log/dataset.
- Strip known noise (build chatter, warnings) so it doesn't crowd the signal.
- If output is large but you might need parts later, redirect it to a file and
  read only the slice you need, when you need it.

## Offload to the filesystem

Use files as memory instead of the context window. Write scratch scripts,
intermediate results, and long artifacts to a scratchpad/temp path; reference
them by path and re-read just the relevant slice later. A path is cheap to carry;
a pasted 500-line blob is not.

## Load just-in-time, not just-in-case

Pull in a file, doc, or reference at the moment the task reaches it — not
speculatively at the start. Most "let me load everything first" reads are never
used and just add noise. Fetch on demand.

## On long/multi-step tasks, keep a compact working state

As a session grows, track a short running state — what's done, what's next, key
decisions and values — rather than re-deriving it from the full history each turn.
When you catch yourself scrolling back through the whole transcript to reconstruct
context, that's the signal to distill it into a few lines instead.

## Hand off to a new session

- Suggest a new session at a new feature or spec, after a unit of work is
  committed, or when the context is mostly exploration the next task doesn't
  need. Write the handoff first.
- Before a session stops mid-task, write the handoff to a file the next session
  can read (a session scratchpad is not one) and give the user its path:
  scope, decisions, status, next step, changed files, verification commands with
  their results, and approvals still open.
- Picking up a handoff, re-check `git status` and re-run the verification before
  trusting it. An approval in the old conversation is not an approval now.

## Guards

- Where the context hooks are installed, a nudge flags a session grown long and
  a guard refuses whole reads of long files; work as if they weren't there.
- Where rtk is installed, it compresses shell output; filter yours anyway.
