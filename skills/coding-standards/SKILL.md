---
name: coding-standards
description: >-
  Production-level coding standards for backend work. Use this WHENEVER writing or
  editing code, adding a dependency, creating a new module, organising packages,
  or running quality checks — trigger on any file edit, package install, or review
  of code structure. Keep modules small and focused, reuse before adding, name
  things professionally, type-hint and document every function, comment the WHY
  not the what, use the repo's existing tooling (uv/poetry, ruff etc for Python),
  and lint after every change. Aim for the smallest change that reads like the surrounding code.
---

# Coding standards

Write code to production standards: small, focused, well-named, and consistent
with what's already there. The bar is code a senior engineer would approve in
review without comments. Before writing, read enough of the surrounding code to
**match its idiom** — naming, structure, comment density, error handling. New code
should look like it was always there, not like it was pasted from elsewhere.

**Vocabulary note:** examples below use Python terms: *module* = source file,
*subpackage* = directory of modules. Substitute your language's equivalent:
file/directory in TS/JS, file/package in Go and Java, file/module in Rust
(with `mod.rs`), etc. The principles are the same.

## Use the repo's existing tooling

Don't introduce new tools — find what the repo already uses and use it:

- **Dependencies & commands** through the project's manager (`uv`/`poetry` in Python,
  `npm`/`pnpm`/`yarn` in JS/TS, `go mod` in Go, `cargo` in Rust, etc.) — check the project's manifest and lockfile first. Never `pip install` into a `uv` project.
- **Format & lint after every change** with the repo's configured tool (`ruff format`, `ruff check`,
  etc.) — run it before considering an edit done, and run the type checker / tests
  if the repo has them. Adding a dependency is itself a real decision — keep it
  minimal (see the `dependency-safety` skill).

## Small, focused modules

- Aim for **under ~200 lines per file**. When a file grows past that, it's usually
  doing too much — split it along its natural seams. When the pieces cluster
  around one theme, promote them into a subpackage (a directory with `__init__.py`).
  A long file is a smell that a concept is hiding inside another.
- **One concept per module, one theme per subpackage.** Name each for what it
  holds — `parsers.py`, not `utils_and_helpers.py`; `billing/`, not `misc/`.
  `utils`/`helpers`/`common`/`shared`/`misc` at either level is where cohesion
  goes to die — give things a real home.
- **Group by feature, not by layer-within-layer.** Keep the things that change
  together close together.

## Use config files

Don't hardcode parameters within random scripts.

- **Config files**: set up a config file for the repository (or a config subpackage if more appropriate), where you can introduce
  relevant constants and parameters.
- **Env variables**: only use environment variables for secrets such as API keys, seed phrases, RPC nodes etc.
  Always ensure these are gitignored.
- **CLI parameters**: for scripts that use CLI arguments, do not overcrowd -- allow tunable configs via CLI only for a small set of
  very important parameters.

## Reuse before adding

Before writing a new function/class/module, ask **"does this already exist?"**
Duplicated logic (three functions doing the same thing) is a maintenance trap.

- If it exists, use or extend it. If it doesn't, decide **which existing place it
  belongs in** rather than defaulting to a new file.
- If the honest answer is "a new top-level package," the feature is probably big
  enough to deserve one — but **flag that before creating it**, don't do it silently.

## Naming

Names are the cheapest documentation — spend care on them.

- **Functions: short, ~3 words max.** If you need more, the function is usually
  doing too much — split it. (`parse_row`, not `parse_row_and_validate_and_store`.)
- **Variables: descriptive but concise** — `pending_rows`, not `pr` and not
  `the_list_of_pending_rows`.
- **Classes: noun phrases** — `BankParser`, `MerchantMapping`, `ParsedTransaction`.
- **Modules: `snake_case`, single concept** (see above).

## Type hints and docstrings

- **Type-hint every function signature** — parameters and return. Types are
  checkable documentation and catch whole classes of bugs.
- Give each function a **one-line description** of what it does; **docstrings on
  public functions and classes** (a single line is fine when a single line says it).
  Skip docstrings on trivial private helpers whose name already says everything.

## Comments

The code already shows *what* it does; comments explain *why* — the reason this
approach was chosen, a non-obvious constraint, or why a simpler-looking option
would be wrong. A comment restating the code is noise.

- Keep comments **objective and professional** — as if they were always part of the
  codebase. Never conversational meta ("as requested", "as you asked", "fixed the
  bug you mentioned") and never review/planning artifacts (priority tags like
  `P1`/`B2`, "TODO from review") left in source.
- Note genuine quirks and gotchas (e.g. a preserved upstream typo, a workaround for
  a known bug) so the next reader doesn't "fix" them.

## Keep the diff minimal and clean

- Change only what the task needs. **Don't reformat or refactor unrelated code** —
  it buries the real change and burdens review.
- **Remove dead code; don't comment it out.** Version control is the history.
- Don't leave debug prints, stray scaffolding, or half-finished alternatives behind.

## Verify before done

Run the repo's lint/format, type checks, and tests after the change. "It should
work" isn't done — a clean lint + type pass (and green tests, where they exist) is
the minimum before calling an edit complete.
