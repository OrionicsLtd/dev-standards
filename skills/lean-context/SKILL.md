---
name: lean-context
description: >-
  Practices for keeping the context window lean while working. Apply at the START
  of any task that involves exploring, understanding, editing, or debugging a
  codebase, and BEFORE reading files or running commands that dump large output.
  Scout with search instead of reading whole files, delegate broad multi-file
  exploration to subagents, read only the slices you need, never re-read what's
  already in context, filter command output, and offload intermediates to the
  filesystem.
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

## Don't re-read

Don't re-open files already in context, and don't re-run a search whose answer you
already have.

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
