---
name: spec-writing
description: >-
  Write a specification or design doc before building a feature, refactor or
  pipeline change. Use whenever asked to write, draft or plan a spec, design doc
  or implementation plan, or before starting work large enough to need one
  (several modules, a new command or stage, a data-format change). A spec here
  is short and testable: numbered requirements, each with an acceptance test that
  is written before the implementation, plus the wiring and docs the change must
  touch.
---

# Spec writing

A spec exists so that "done" can be checked. Every requirement must be one a test
or a command can confirm; anything that can't be checked is a note, not a
requirement. Keep it short — one to three screens. Put it where the repo keeps
specs (e.g. `docs/specs/`), and match their existing format if one exists.

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
   expected output, and the test's name. Add **properties** where they exist
   (round-trip, idempotence, ordering, conservation, "never more than N") —
   they become property-based tests. Every acceptance test must run offline
   and free: mock or record any paid model or API call.
6. **Edge cases** — empty, missing, duplicate, boundary, concurrent, malformed.
   Each one either maps to a requirement or is explicitly out of scope.
7. **Wiring** — every entry point that must reach the new behaviour (CLI,
   registry, orchestrator, config) and every doc, skill, prompt or README that
   describes the area and must change with it. This list is what the reviewer
   checks the diff against.
8. **Open questions** — decisions the user must make. Resolve them before
   implementing (see `clarify-first`).

## Building from a spec

1. Write the acceptance tests first and watch them fail for the right reason.
2. Implement until they pass; add tests for edge cases found on the way.
3. Walk the Wiring list; exercise the change through its real entry point at no
   cost (dry run, fixtures, recorded responses — never a paid call).
4. Run `diff-reviewer` with the spec path; it maps each requirement to code.
5. If the implementation had to deviate, update the spec in the same change —
   a spec that disagrees with the code misleads the next reader.

Requirement ids live in the spec only. Code, comments and test names describe
behaviour (`test_merge_keeps_newest_entry`), never `R3` or the spec section.
