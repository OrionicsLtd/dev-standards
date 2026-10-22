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

- Aim for **under ~200 lines per file**; **400 is the hard limit** (the devgate Stop hook
  blocks a change that pushes a file past it). A file past 200 is usually doing too
  much — split it along its natural seams. When the pieces cluster
  around one theme, promote them into a subpackage (a directory with `__init__.py`).
  A long file is a smell that a concept is hiding inside another.
- Prefer nesting over a flat pile. A new module belongs in a themed subpackage
  (`<pkg>/<theme>/thing.py`), not as yet another file at the package root.
  Adding the ~5th flat script to a directory is the signal to group the existing
  ones into subpackages first.
- **One concept per module, one theme per subpackage.** Name each for what it
  holds — `parsers.py`, not `utils_and_helpers.py`; `billing/`, not `misc/`.
  `utils`/`helpers`/`common`/`shared`/`misc` at either level is where cohesion
  goes to die — give things a real home.
- **Group by feature, not by layer-within-layer.** Keep the things that change
  together close together.

## Reuse before adding

Before writing a new function/class/module, ask **"does this already exist?"**
Duplicated logic (three functions doing the same thing) is a maintenance trap.

- If it exists, use or extend it. If it doesn't, decide **which existing place it
  belongs in** rather than defaulting to a new file.
- If the honest answer is "a new top-level package," the feature is probably big
  enough to deserve one — but **flag that before creating it**, don't do it silently.

## Use config files

Don't hardcode parameters within random scripts.

- **Config files**: set up a config file for the repository (or a config subpackage if more appropriate), where you can introduce
  relevant constants and parameters.
- **Env variables**: only use environment variables for secrets such as API keys, seed phrases, RPC nodes etc.
  Always ensure these are gitignored.
- **CLI parameters**: for scripts that use CLI arguments, do not overcrowd -- allow tunable configs via CLI only for a small set of
  very important parameters.

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
  bug you mentioned"), never history ("now", "previously", "after the refactor"),
  and never review/planning artifacts (priority tags like `P1`/`B2`, work-package or
  phase numbers, spec sections, "TODO from review") left in source. No section banners.
- A docstring or comment that describes behaviour the code no longer has is a bug.
  Update or delete it in the same change.
- Note genuine quirks and gotchas (e.g. a preserved upstream typo, a workaround for
  a known bug) so the next reader doesn't "fix" them.

## Design: functional core, imperative shell

The principles of *Functional Programming in Scala*, applied in the host language's
own idiom — no FP libraries, monad stacks or point-free tricks.

- **Pure core, effects at the edges.** Logic is functions from inputs to outputs.
  File, network, clock, randomness and environment access live in a thin outer
  layer that calls the core and passes values in. A function that both decides
  and does I/O should usually be two.
- **Referential transparency.** A function's result depends only on its arguments:
  no reads of mutable module state, no hidden caches that change answers.
- **Immutable data.** Frozen dataclasses / frozen pydantic models, tuples; return a
  new value instead of mutating an argument. Mutation local to a function that
  nobody else can observe is fine.
- **Make illegal states unrepresentable.** Model alternatives as `Enum`/`Literal`
  or a union of dataclasses handled with `match` (and `assert_never` for
  exhaustiveness), not string flags and clusters of optional fields. Parse
  untrusted input once at the boundary into precise types; the core never
  re-validates.
- **Total functions, errors as values.** Handle every input. Where failure is an
  expected outcome, return it in the type (a result union, an explicit `None`
  with a documented meaning); raise only for bugs and truly exceptional
  conditions, and catch at the boundary.
- **Composition.** Small functions combined; comprehensions and generators over
  index loops; split a function rather than add a boolean mode flag.
- **Laws, then tests.** State the properties an API must keep (round-trip,
  idempotence, ordering, conservation) and test them with property-based tests
  (Hypothesis in Python) alongside examples.

## Keep the diff minimal and clean

- Change only what the task needs. **Don't reformat or refactor unrelated code** —
  it buries the real change and burdens review.
- **Remove dead code; don't comment it out.** Version control is the history.
- Don't leave debug prints, stray scaffolding, or half-finished alternatives behind.

## Verify before done

Run the repo's lint/format, type checks, and tests after the change, then exercise
it through its real entry point without spending money (dry runs, fixtures,
mocked or recorded responses; never paid API or model calls). "It should work"
isn't done; see the global
CLAUDE.md for the full definition of done and the report format.
