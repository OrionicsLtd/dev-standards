# Skills backlog

Improvements drawn from comparing this repo with addyosmani/agent-skills. Scaffolding:
delete this file once every item is done or dropped.

Ground rules:

- No new skills. Each skill stays narrow; every skill's description is loaded in every
  session, so descriptions stay short and must not collide.
- One section below = one session. Sections touch disjoint files so they can run in
  parallel; README rows are updated in the final sweep, not per session.
- Build with our own skills: `spec-writing` for the code-bearing sections (1, 7b, 8),
  `testing`, and `diff-reviewer` before reporting.

## 1. devgate: floor guard, secrets, missing tools — `hooks/devgate/**`

- [ ] Block suppressions added without a reason on the same line: `# noqa`,
  `# type: ignore`, `# pyright: ignore`, `pragma: no cover`, `pytest.mark.skip`/`xfail`.
  `# noqa: BLE001 - a broken gate must not wedge the session` passes.
- [ ] Secret check: a style rule beside `banned()`, run on session-written lines in the
  Stop hook, no new dependency. Reports `path:line` and the kind of secret only, never
  the matched text (`banned()` echoes 60 chars, `style.py:71`). Patterns: known key
  prefixes, PEM private keys, 64-hex keys, 12/24-word mnemonics.
- [ ] A check whose binary is missing must not count as passed or drop out of the
  summary (`checks.py:52`, `gate.py:100`).
- Deferred: blocking session edits to `.claude/devgate.toml`; ignoring tests that were
  already failing at session start.

## 2. Fixing a bug — `skills/testing/SKILL.md`

- [ ] "Fixing a bug" section: reproduce with a failing test first; for a regression,
  localise with `git bisect run <test>`; fix the cause, not the symptom; decide whether
  the test or the code is wrong before changing either; a flaky test is a bug, not a
  re-run; state competing hypotheses and the check that separates them; remove debug
  instrumentation once the test guards the fix.
- [ ] Description also triggers when an error, traceback or failing test is pasted, or
  the fix looks obvious.
- [ ] A crash, atomicity or rollback claim is tested by killing the process and reopening
  the store, not by a mock or an injected exception.
- [ ] Tests pass in any order: no shared mutable state between them.

## 3. diff-reviewer — `agents/diff-reviewer.md`

- [ ] Label defects that predate the change separately from ones it introduces.
- [ ] Incompatible change to an existing flag, output column, file or JSON shape.
- [ ] Per-row I/O inside a loop; unbounded reads or fetches.
- [ ] Weakened checks devgate cannot see: deleted tests, removed asserts, loosened
  ruff, pyright, pytest or coverage config.

## 4. Grill before the spec; ask, don't assume — `skills/spec-writing`, `skills/clarify-first`

- [ ] `spec-writing` step 0: grill the user before drafting — one question at a time,
  each with a best guess, until goal, non-goals and edge-case categories are settled;
  stop once the answers become predictable.
- [ ] `spec-writing`: a data-format change states whether old files and caches still
  read, and how to roll back.
- [ ] `spec-writing`: a request holding independently testable capabilities is split
  into one spec per capability, with the build order agreed first.
- [ ] `clarify-first`: "whatever you think" or "sounds good" does not settle a real
  fork; re-ask as two concrete options.
- [ ] `clarify-first`: when the user can't be reached, a subagent stops and returns the
  question to its caller, which asks the user; an unattended run (loop, schedule) holds
  that step, finishes the rest and reports the question. Never settle it by assumption.
- [ ] `clarify-first`: push back on a clear instruction that is a bad idea — name the
  concrete cost and the alternative, then follow the user's informed call.

## 5. coding-standards — `skills/coding-standards/SKILL.md`

- [ ] Build for the requirement in hand: no parameter, hook or abstraction with one
  caller "for later"; extract a helper on the third repetition.
- [ ] Never silence a check to pass it; a suppression names the rule and the reason on
  its line (the rule devgate enforces in section 1).
- [ ] Model output is untrusted input: parse it against a schema at the boundary; never
  pass it to a shell, SQL, a file path or `eval`.

## 6. Working agreement — `CLAUDE.md` (and the user-level copy)

- [ ] Report adds two lines: problems noticed but left alone, and sibling paths ruled out.
- [ ] Brief a reviewer with the request, the spec path and evidence; never with your own
  summary or reasons the change is right.
- [ ] Commits: none while work is in progress. Once `diff-reviewer` passes, suggest the
  commit, or several when the change holds separate logical units, each with its
  message (`type: summary`, then a body that says why).

## 7. Sessions and output — `skills/lean-context/SKILL.md`

- [ ] Handoff: before a session stops mid-task, write scope, decisions, status, next
  step, changed files, verification commands with results and open approvals to a file;
  the next session re-checks `git status`, re-runs verification and never infers an
  approval from the old conversation.
- [ ] Suggest a new session at a new feature or spec, after a unit of work is committed,
  or when the context is mostly exploration the next task doesn't need; write the
  handoff first.
- [ ] Subagent briefs: paths instead of pasted content, the size of answer wanted, a
  cheaper model for read-only search.
- [ ] Don't re-run a command on unchanged code.
- [ ] Our scripts print a short summary and write details to a file: audit
  `run_advisories.py scan`/`hot` and devgate's block messages.

## 7b. Context hooks — new `hooks/context/` package, `settings.example.json`

rtk (a `PreToolUse` Bash hook in `~/.claude/settings.json`) already compresses shell
output. These cover what it never sees: the Read tool and session length.

- [ ] Context nudge (`UserPromptSubmit`): read the last assistant `usage` from
  `transcript_path` (input + cache read + cache creation = live context). Above 300k
  tokens (configurable), add context: "~N tokens in use; if this request is a new task,
  propose a new session and write the handoff first."
- [ ] Whole-file read guard (`PreToolUse` on Read): a text file over ~400 lines read
  without `offset`/`limit` is denied with its line count and "grep, then read the slice".
  An explicit `limit` reads it all on purpose. Verify before building:
  - Edit and Write still accept a file that was only read in part; if not, the guard
    forces the full reads it is meant to prevent.
  - Whether hook input identifies a subagent; if it does, skip subagents, whose context
    is thrown away (`diff-reviewer` reads new files whole by design).
  - Skip images, PDFs and notebooks; line counts mean nothing for them.

## 8. Evals and lint for this repo — new `tests/`, `evals/`

- [ ] Offline routing eval: `evals/<skill>.json` holds prompts that must route to the
  skill and negatives naming the skill that should win; TF-IDF over descriptions; fails
  on colliding descriptions. pytest, no model calls.
- [ ] Lint: skill name matches its directory, description length, no dead skill
  references, reviewer name agrees across the agent file, `gate.py` `REVIEWER` and the
  `SubagentStop` matcher.
- Runs after 2 and 4, which change descriptions. Adding `tests/` puts this repo under
  devgate.

## 9. Small skill edits — `skills/docs-maintenance`, `skills/dependency-safety`

- [ ] `docs-maintenance`: rewriting a doc keeps its names, numbers, commands and caveats;
  never replace an unsupported claim with an invented one; flag commands you couldn't run.
- [ ] `dependency-safety`, one line: before adding a package, check it is maintained and
  is the package you meant (typosquats); a Python sdist runs code at install.

## 10. Final sweep — `README.md`

- [ ] Skill table, quality-gate section and "Try it" rows match the changes above.
- [ ] Recommend rtk (https://github.com/rtk-ai/rtk) under Installing: what it covers
  (Bash output only), the `PreToolUse` hook line, `rtk recall` and `rtk proxy` for when
  the filter hides something, telemetry off by default. Recommended, not required.

## Dropped or deferred

- Alternatives-considered section in specs; hostile-input edge-case category.
- Trust-boundary security pass in `diff-reviewer` (left to `/security-review`).
- DAMP over DRY in tests; logging and performance rules in `coding-standards`.
- Idempotency rules, until payments or on-chain work.
- Repeat-run guard; committing per slice on branches; end-to-end tests.
