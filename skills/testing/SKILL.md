---
name: testing
description: >-
  Write and organise tests. Use whenever writing, changing or reviewing tests,
  fixing a bug, or choosing the acceptance tests for a spec. Two levels: unit
  tests on the pure core, integration tests through the real entry point with
  fakes only at the I/O edge; no end-to-end tests against live services. Every
  test must be able to fail and must pass on a clean checkout.
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
- A bug fix gets a test at the lowest level that reproduces it.
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

## Every test

- **Watch it fail first.** Write the test before the code and run it: it must fail
  for the right reason. For a bug fix, revert the fix once and see the test fail;
  for code that already works, break the behaviour once, see the test fail, restore.
- **Test behaviour.** Assert what a caller can observe (return values, CLI output,
  files written), not private helpers or the wording of prompts and docs.
- **Derive expected values independently.** Write the arithmetic in the test
  (`1000 + 300 - 75 - 100`) or use a hand-checked worked example; never compute
  the expectation with the code under test or copy numbers from a run.
- **No tests that cannot fail:** `is not None` or type-only asserts, a pure function
  called twice to prove determinism.
- **A clean checkout passes the suite.** Never read gitignored, hand-kept or live
  data, the network or the clock; use committed fixtures.
- **One behaviour per test**, named for it (`test_merge_keeps_newest_entry`); use
  table-driven cases (pytest's `parametrize`) rather than a loop.
- **Layout follows the repo.** Where there is none, keep integration tests in their
  own directory so each level can run alone.
