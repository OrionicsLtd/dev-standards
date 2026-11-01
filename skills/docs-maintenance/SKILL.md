---
name: docs-maintenance
description: >-
  Keep specs, design docs, plans and READMEs true as the code changes. Use
  whenever a change alters behaviour a doc describes; when building from,
  finishing, superseding or abandoning a spec or plan; when adding, moving or
  tidying docs; and before relying on a spec to understand code. Covers the specs
  index, status and supersede markers, folding deviations back into the spec,
  and checking a doc against the code before trusting it.
---

# Docs maintenance

A doc that disagrees with the code is worse than none: the next reader trusts it.
Keep one source of truth per fact, and change it in the same commit as the code.

## One index

- Every spec and design doc is listed in one index (e.g. `docs/specs/README.md`)
  with a one-line description and its status. A doc goes into the index in the
  change that adds it; a doc missing from the index is a bug.
- The index carries nothing that needs hand-dating ("Updated on …"); git has it.

## Status at the top, in one form

Each spec opens with its status in the same form across the repo. Match the
repo's convention; if it has none, propose this frontmatter to the user before
adopting it:

```yaml
---
status: draft | specced | partly built | built | superseded | abandoned
description: One line, the same text the index shows.
superseded_by: docs/specs/new-spec.md      # only when superseded
code: [src/pkg/module.py, src/pkg/cli.py]   # what implements it
verified: abc1234                           # commit it was last checked against the code
---
```

When work lands, update the status and the index row together.

## Keep the spec true while building

- When the implementation deviates, change the requirement itself, not an "as
  built" note on top. History lives in git.
- A plan (build order, phases, task lists) is scaffolding. Once the work is built,
  fold any design change into the spec, then delete the plan or mark it done. Two
  docs must never both claim to be the truth about the same behaviour.
- No live state in specs: dated figures, balances and "as of" tables go stale.
  They belong in generated output or the command that produces them.

## Superseding and retiring

- When a new spec replaces an old one, mark the old one `superseded` with a
  pointer to the new, and say in the new one what it replaces. Repoint links that
  cite the old spec for current behaviour.
- Keep a superseded or abandoned spec while other docs link to it; delete it once
  nothing does — git keeps it.

## Before trusting a doc

- Check whether the code it describes changed since it was last verified:
  `git log --oneline <verified commit>.. -- <code paths>`. If it did, read the code
  before relying on the doc, and fix whichever is wrong.
- When `diff-reviewer`'s spec coverage or your own check confirms a spec matches
  the code, update `verified`.

## Other docs

READMEs, CLAUDE.md files, skills, prompts and command help describe behaviour
too. When a change renames or alters something, grep for the old name across them
and update each in the same change. A doc's claim about a command (flags,
output) should be checkable: run `--help` or the command on a fixture.

## Sweep

When asked to tidy docs, or before starting work in an area, compare:

- docs on disk against the index, and each status against `git log`;
- relative links against the files they point to;
- test names the specs list against `pytest --collect-only -q`;
- `code:` paths against the tree.

Report what disagrees and fix it in one change.
