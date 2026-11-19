---
name: testing
description: >-
  Write and organise tests. Use whenever writing, changing or reviewing tests,
  or fixing a bug, including a pasted error, traceback or failing test, or a
  fix that looks obvious. Two levels: unit tests on the pure core, integration
  tests through the real entry point with fakes only at the I/O edge; no
  end-to-end tests against live services. Every test must be able to fail and
  must pass on a clean checkout.
---

# Testing

## Levels

| Level | Covers | Test doubles |
| --- | --- | --- |
| Unit | Functions of the pure core: examples, edge cases, properties. | None needed. |
| Integration | Units wired together, driven through the real entry point (CLI in-process or as a subprocess, public API, pipeline stage) on committed fixtures. | Fakes or recorded responses at the I/O edge only (see below). Real filesystem in a temp dir. |

- Logic, branches and edge cases go in unit tests; most tests live there.
- Laws an API must keep (round-trip, idempotence, ordering, conservation) become
  property-based tests (Hypothesis in Python) alongside examples.
- **A change to what an entry point accepts or does (a command, flag, step or
  output) gets an integration test that reaches it from the entry point.** Test
  there what only the wiring can break: parsing, step order, what is written or
  printed, exit codes, errors crossing modules. Don't re-test the units' branches.
- No end-to-end tests: none that touch live services, deployed systems, real
  accounts or paid APIs. They cost money, flake, and can't run on a clean
  checkout. A check against real data is a script, or a test that skips with a
  reason when the data is absent and has an offline counterpart.

## Test doubles

- Fake only the I/O edge: network, paid APIs, clock, randomness, and local tools
  the suite can't assume are installed (feed their recorded output). Tools it can
  assume, like git, run for real in a temp dir; set environment variables per test.
- Never mock the repo's own modules. Code that is hard to test without mocking
  them has logic in the shell; move it into the core.
- Prefer in-memory fakes and recorded responses to mock objects. Assert on
  outcomes, not on which methods were called.
- A recorded response is a real one captured once, trimmed and scrubbed of
  secrets, and committed.
- A crash, atomicity or rollback claim is tested by killing the process and
  reopening the store, not by a mock or an injected exception.

## Every test

- **Watch it fail first.** Write the test before the code and run it: it must fail
  for the right reason. For code that already works, break the behaviour once,
  see the test fail, restore.
- **Test behaviour.** Assert what a caller can observe (return values, CLI output,
  files written), not private helpers or the wording of prompts and docs.
- **Derive expected values independently.** Write the arithmetic in the test
  (`1000 + 300 - 75 - 100`) or use a hand-checked worked example; never compute
  the expectation with the code under test or copy numbers from a run.
- **Test the rule, not the sample.** Unless the user's examples are the full
  list (see `clarify-first`), the examples in a request or spec are some of the cases,
  not all of them. Add cases the code was not written from (other
  members of the category, the boundaries) or a property, so an implementation
  that special-cases the examples fails.
- **No tests that cannot fail:** `is not None` or type-only asserts, a pure function
  called twice to prove determinism.
- **A clean checkout passes the suite.** Never read gitignored, hand-kept or live
  data, the network or the clock; use committed fixtures.
- **Tests pass in any order:** no mutable state shared between them.
- **Shared builders live in `conftest.py` or a helper module** under the tests
  directory, never in a `test_*` module another one imports. When a test needs a
  sibling's helper, move the helper there.
- **One behaviour per test**, named for it (`test_merge_keeps_newest_entry`); use
  table-driven cases (pytest's `parametrize`) rather than a loop.
- **Layout follows the repo.** Where there is none, keep integration tests in their
  own directory so each level can run alone.

## Fixing a bug

- **Reproduce it first:** a failing test at the lowest level that shows the bug,
  written before the fix, even when the fix looks obvious. If the fix is already
  in, revert it once and see the test fail.
- **Decide whether the test or the code is wrong** before changing either.
- **Name the competing explanations** and the check that tells them apart; run
  it before choosing one.
- **For a regression, find the commit:** `git bisect run` a wrapper around the
  new test that exits 125 where the test cannot run, since bisect counts any
  other exit from 1 to 127 as the bug. Leave the test untracked so every
  checked-out commit runs it; commit it with the fix.
- **Fix the cause, not the symptom:** no special case for the failing input, no
  swallowed error, no retry around it.
- **A flaky test is a bug** in the test or the code; find it, don't re-run.
- **Remove debug instrumentation** once the test guards the fix.

## Relaxed for tests

`coding-standards` applies, except:

- No file-size limit. devgate skips anything under `tests/` or a `test_*` file or
  directory at any depth, plus `*_test.*`, `*.test.*`, `*.spec.*` and `conftest.py`
  (pytest's convention, so a production `test_mode.py` is skipped too). Split a file by the behaviour
  under test once it is hard to navigate.
- Test names are as long as the behaviour they state; no docstring when the name
  says it all.
