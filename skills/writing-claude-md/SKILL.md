---
name: writing-claude-md
description: >-
  Write, review and maintain CLAUDE.md and AGENTS.md instruction files —
  user-level, project, local, subdirectory and path-scoped `.claude/rules/`. Use
  whenever creating, editing, trimming or reviewing one of these files; when the
  user says "add this to CLAUDE.md", "remember to always …" or "from now on …";
  or when the same correction has come up twice in a project.
---

# Writing CLAUDE.md

CLAUDE.md is delivered as a user message in every session and stays in context:
every line costs tokens on every turn and competes for attention. It is guidance,
not enforcement. Put in it only what Claude would get wrong without it and cannot
find quickly in the code.

## Where an instruction belongs

| Instruction | Goes in |
| --- | --- |
| Your working style, in every repo | `~/.claude/CLAUDE.md` |
| Everyone working in this repo | `./CLAUDE.md` or `./.claude/CLAUDE.md`, committed |
| Only you, only this repo | `./CLAUDE.local.md`, gitignored |
| Only one area of the code | a `CLAUDE.md` in that directory, or `.claude/rules/<name>.md` with `paths:` frontmatter |
| A multi-step procedure | a skill |
| Something that must happen at a set point, every time | a hook |
| Permissions, environment, tools | settings |

Files in the working directory and above load at launch, and the root CLAUDE.md
and unscoped rules are re-injected after compaction. Subdirectory CLAUDE.md files
and `paths:` rules load when Claude reads or edits a matching file and are
dropped at compaction until touched again — a rule that must always hold goes in
the root file. AGENTS.md is read only when no CLAUDE.md exists; in a repo with
both, keep the shared rules in one and import it from the other (`@AGENTS.md`).

## What a project CLAUDE.md holds

- **Exact commands** that work here: setup, test, lint, type-check, run
  (`uv run pytest -q`, not "run the tests").
- **A short map**: the top-level packages and what each does; where specs, docs
  and fixtures live, with a link to the specs index.
- **Conventions that differ** from the defaults or the user-level file, each with
  its reason.
- **Hard constraints**: data never committed or read by tests, calls that cost
  money, generated files never edited by hand, systems never touched.
- **How work is verified here** when it takes more than the commands: fixtures,
  dry-run flags, the live check left to the user.

## What stays out

- Anything the user-level file or a skill already says.
- The content of specs and docs — link to them instead.
- What a linter, formatter, test or hook already enforces.
- History, dated state, changelogs, plans and aspirations.
- Advice true of any repo ("write clean code").

## How to write it

- Imperative and specific, one rule per bullet, with its reason when that is not
  obvious.
- Stay under 200 lines; a good project file is often 30–80.
- `@path` imports are expanded at load (up to four hops deep), so they organise
  the file without saving context. Name a file in prose instead when it should be
  read only when needed.
- Block-level `<!-- … -->` comments are stripped before Claude sees the file;
  notes for human maintainers go there.

## Keeping it current

- When the same correction comes up a second time, add a line — the rule, not
  the incident.
- When a command, path or convention it names changes, update it in the same
  change.
- Remove lines that no longer change behaviour: superseded rules, rules now
  enforced by a hook or check.
- After editing, run every command it lists and check every path it names.
- `/init` drafts a file or suggests improvements to an existing one, and
  `/doctor prompt-audit` (Claude Code 2.1.283+) reports outdated or conflicting
  instructions; treat both as input and edit by these rules.
