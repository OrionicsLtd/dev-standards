---
name: spec-writing
description: >-
  Write a specification or design doc before building a feature, refactor or
  pipeline change. Use whenever asked to write, draft or plan a spec, design doc
  or implementation plan, or before starting work large enough to need one
  (several modules, a new command or stage, a data-format change). A spec here
  is testable: numbered requirements, each with an acceptance test that is
  written before the implementation, the domain rules and data sources the
  change depends on, and the wiring and docs it must touch.
---

# Spec writing

A spec exists so that "done" can be checked. Every requirement must be one a test
or a command can confirm; anything that can't be checked is a note, not a
requirement. Put it where the repo keeps specs (e.g. `docs/specs/`), match their
existing format if one exists, open it with the repo's status header, and add it
to the specs index (see `docs-maintenance`). An implementation plan is a build
order within the spec, or a temporary companion folded back into it once built.

## Structure

1. **Goal** — the problem, in two or three sentences, and who it is for.
2. **Non-goals** — what this deliberately does not do. Prevents scope creep and
   tells the reviewer what not to flag.
3. **Interface** — signatures, CLI commands and flags, file and data shapes,
   config keys. Concrete enough to write tests against. Design the operations
   and their laws first (what composes with what, what must always hold), then
   the types.
4. **Requirements** — numbered `R1`, `R2`, … Each is one observable behaviour:
   "given X, the command does Y". Include the failure behaviour, not just the
   happy path.
5. **Acceptance tests** — for each requirement, the test that proves it: input,
   expected output, the test's name and its level (unit, or integration
   when the requirement changes what an entry point accepts or does). Work
   expected values out independently of the code (the arithmetic, or a hand-checked example). Add **properties**
   where they exist (round-trip, idempotence, ordering, conservation, "never more
   than N") — they become property-based tests. Every acceptance test must run
   offline and free: mock or record any paid model or API call. The rules for
   good tests are in `testing`.
6. **Edge cases** — empty, missing, duplicate, boundary, malformed, concurrent
   (including parallel agents or workers writing the same files). Each one either
   maps to a requirement or is explicitly out of scope.
7. **Data and domain** — whichever of these the change depends on:
   - *Domain rules*: each limit, formula, threshold or external fact, with its
     source, the requirements that apply it, every code path that must apply
     it, and a worked example. A rule is usually missed in the second place it
     applies.
   - *Sources*: where each input comes from (command, API, file), who maintains
     it (committed, gitignored, hand-kept), its limits (pagination, rate limits,
     freshness), and the recorded fixture tests use instead.
   - *Numbers*: units, rounding, decimal or float, time zone, which day's rate.
   - *Determinism boundary*: when a skill, agent or prompt presents figures, the
     command that produces each one. The model selects, quotes and judges; it
     never computes.
8. **Wiring** — every entry point that must reach the new behaviour (CLI,
   registry, orchestrator, config) and every doc, skill, prompt or README that
   describes the area and must change with it, the specs index included. This
   list is what the reviewer checks the diff against.
9. **Open questions** — decisions the user must make. Resolve them before
   implementing (see `clarify-first`).

## Building from a spec

1. Have the spec reviewed: run `spec-reviewer` with the user's request and the
   spec path, and wait for its result. Resolve what it confirms and the open
   questions before writing tests.
2. Write the acceptance tests first — unit by unit when the spec has several —
   run them and see each fail for the right reason before writing the code it
   covers. List that failing run among the commands in the report.
3. Implement until they pass; add tests for edge cases found on the way.
4. Walk the Wiring list; exercise the change through its real entry point at no
   cost (dry run, fixtures, recorded responses — never a paid call).
5. Run `diff-reviewer` with the spec path; it maps each requirement to code.
6. If the implementation had to deviate, change the requirement itself in the
   same change — not a note on top — and update the spec's status and the index.
   A spec that disagrees with the code misleads the next reader.

Requirement ids live in the spec only. Code, comments and test names describe
behaviour (`test_merge_keeps_newest_entry`), never `R3` or the spec section.
