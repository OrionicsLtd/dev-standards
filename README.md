<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/orionics-lockupA-paper-blue-on-ink.png">
    <img src="assets/orionics-lockupA-ink-blue.png" alt="Orionics" width="320">
  </picture>
</p>

<h1 align="center">dev-standards</h1>

<p align="center">
  Engineering standards for <a href="https://claude.com/claude-code">Claude Code</a>,
  with skills that guide how Claude works and a quality gate that checks the result.
</p>

<p align="center">
  <a href="#try-it">Try it</a> ·
  <a href="#skills">Skills</a> ·
  <a href="#quality-gate">Quality gate</a> ·
  <a href="#installing">Installing</a>
</p>

---

This repository holds the working practices we follow at Orionics Ltd, written so
that Claude Code picks them up on its own. Nine skills cover how to write code and
tests, when to ask rather than guess, how to keep the context window lean, how to
handle dependencies and security advisories, and how to keep specs, docs and
CLAUDE.md files current. Alongside them
sits a quality gate, made up of hooks, two reviewer agents and a user-level
`CLAUDE.md`, which checks the work against those practices before Claude reports it
as done.

## Quick start

Clone the repository and copy the skills into your user-level Claude directory,
which makes them available in every project:

```bash
git clone https://github.com/OrionicsLtd/dev-standards.git && cd dev-standards
cp -R skills ~/.claude/
```

The quality gate takes a few more steps, described under [Installing](#installing).

## Try it

Skills stay out of the way until a request matches one of them. To see one at
work, paste any of these prompts into a Claude Code session:

| Prompt | Skill | What Claude does |
| --- | --- | --- |
| `Add caching to the API.` | `clarify-first` | It asks about the parts of the scope it can't settle alone, such as which endpoints to cache and how entries are invalidated, and states the small assumptions it makes along the way. |
| `Write a spec for adding a --dry-run flag to the export command.` | `spec-writing` | It asks the questions the spec depends on, one at a time, then writes numbered requirements, gives each one an acceptance test, and has `spec-reviewer` check the spec before any test is written. |
| `Write tests for the retry logic in client.py.` | `testing` | It unit-tests the pure logic and adds an integration test through the real entry point, faking only the I/O edge (network, clock, randomness). |
| `This test is failing, here's the traceback.` | `testing` | It reproduces the failure with a test before touching the code, decides whether the test or the code is wrong, and fixes the cause rather than the symptom. |
| `Hand this off to a new session.` | `lean-context` | It writes the scope, decisions, status, next step, changed files and verification results to a file, so the next session starts from that rather than the old conversation. |
| `Upgrade requests to get rid of the warning in CI.` | `dependency-safety` | It makes the smallest change that clears the warning and leaves the rest of the lock file alone. |
| `Is anything here affected by this week's Node.js security release?` | `security-advisories` | It checks what the repository and the machine actually run against live advisory data, then proposes the smallest upgrade that contains the fix. |
| `From now on, always run make lint before committing.` | `writing-claude-md` | It works out whether the rule belongs in CLAUDE.md, a hook or a setting, and puts it there. |

Once the quality gate is installed, devgate holds a turn open when the work falls
short of these standards. Here is its actual reply to a session that had left a
planning note in a code comment:

```text
Fix these before finishing:

Style rules (see CLAUDE.md):
src/export.py:6: comment wording `Phase 2: switch to streaming once the new writer lands`
```

Claude then fixes the comment and tries again. The turn can end once the
repository's checks pass, the style rules are met and the report closes with a
`Not verified:` line. When the session has written 200 or more lines of code or
config that nobody has reviewed yet, `diff-reviewer` has to look at them first. If
devgate blocks three times in a row, it lets the turn end and lists what is still
open.

## Skills

Each skill is a directory with a `SKILL.md` file: YAML frontmatter giving its
`name` and `description`, followed by guidance in Markdown. Claude reads the
description to decide when a skill applies, then follows the guidance while it
works (see the [skills documentation](https://docs.claude.com/en/docs/claude-code/skills)).

| Skill | When it applies and what Claude does |
| --- | --- |
| [`clarify-first`](skills/clarify-first/SKILL.md) | When a task is unclear or could reasonably go more than one way, Claude asks or checks instead of shipping a plausible guess. It also treats examples in a request as a sample of a wider category unless they are clearly the full list, and says so when a clear instruction looks like a bad idea. A vague "sounds good" doesn't settle a real choice, and a subagent or unattended run hands an open question back rather than assuming an answer. |
| [`coding-standards`](skills/coding-standards/SKILL.md) | Whenever Claude writes or edits code, it keeps changes small, well named and type-hinted, matches the code around them, and puts logic in pure functions with I/O kept at the edges. It builds only what the requirement in hand needs, fixes a failing check rather than silencing it, and treats model output as untrusted input. |
| [`dependency-safety`](skills/dependency-safety/SKILL.md) | When a change reaches `pyproject.toml`, a lock file or a Dockerfile, Claude touches a dependency only if it has to and keeps the change small enough to review. Before installing a new package, it checks that the package is maintained and is the one meant, not a typosquat. |
| [`docs-maintenance`](skills/docs-maintenance/SKILL.md) | When a change alters behaviour that a doc describes, or a spec is finished or superseded, Claude keeps the docs true. Specs share one index and carry their status at the top, deviations are folded back into the requirements, and a doc is checked against the code before anyone relies on it. A rewrite keeps the doc's names, numbers, commands and caveats, and never swaps an unsupported claim for an invented one. |
| [`lean-context`](skills/lean-context/SKILL.md) | While exploring or debugging a codebase, Claude searches before it reads, opens only the parts of files it needs, and keeps its context window small. It briefs subagents with paths rather than pasted content and doesn't re-run a command on unchanged code. At a natural break in a long session, it writes a handoff and suggests a new session. |
| [`security-advisories`](skills/security-advisories/SKILL.md) | When you ask about known vulnerabilities or a piece of security news, Claude checks it against what is actually in use and fixes it with the smallest upgrade that contains the fix. It works from free live sources such as OSV, GHSA, NVD, CISA's catalog of exploited vulnerabilities, EPSS and vendor release indexes. Its scans print a short summary and write the full report to a file. |
| [`spec-writing`](skills/spec-writing/SKILL.md) | When you ask for a spec or design doc, or start work big enough to need one, Claude first asks the questions the spec depends on, one at a time. Every requirement is numbered and has an acceptance test written before the implementation. The spec also records the domain rules and data sources the change depends on, and the wiring and docs it touches. A request holding several independently testable capabilities gets one spec each, and a data-format change says whether old files still read and how to roll back. |
| [`testing`](skills/testing/SKILL.md) | When Claude writes, changes or reviews tests, unit tests cover the pure core and integration tests go through the real entry point, with fakes only at the I/O edge and nothing running against live services. When it fixes a bug, it first reproduces it with a failing test, then fixes the cause rather than the symptom. |
| [`writing-claude-md`](skills/writing-claude-md/SKILL.md) | When you create, edit, trim or review a CLAUDE.md, AGENTS.md or `.claude/rules/` file, or say "from now on…", or the same correction comes up twice, Claude works out what belongs in each file rather than in a skill, hook or setting, and keeps the files short and current. |

## Quality gate

Instructions on their own tend to drift over a long session, so the quality gate
checks the work itself.

| Piece | What it does |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | The working agreement Claude loads in every session. It defines what "done" means, how to brief a reviewer (the request, the spec and the evidence, never Claude's own case for the change), and when to suggest commits (once `diff-reviewer` passes, never while work is in progress). It also sets the rules for comments and module size, and fixes the report format, which names the sibling paths ruled out and the problems left alone and ends with a `Not verified:` line. |
| [`agents/diff-reviewer.md`](agents/diff-reviewer.md) | A read-only agent that reviews the uncommitted diff against the user's request and any spec, without seeing the session's context. It runs on Haiku at high effort, which keeps reviews cheap. |
| [`agents/spec-reviewer.md`](agents/spec-reviewer.md) | A read-only agent that reviews a spec against the request and the code it will change, before anything is built. It runs on Sonnet, because design gaps were where Haiku's reviews were weakest. |
| [`hooks/devgate`](hooks/devgate) | A `Stop` hook that holds a turn open while the repository's own checks fail. It also blocks comments written in planning or conversation wording, lint and test suppressions that don't say why, possible secrets, non-test files pushed past 400 lines, new modules that push a package past 15, large changes that haven't been through `diff-reviewer`, and reports that lack their `Not verified:` line. |
| [`hooks/context`](hooks/context) | Two hooks that keep the context window in check. Past 300k tokens, a `UserPromptSubmit` hook tells Claude to propose a new session, with a written handoff, when a request starts a new task. A `PreToolUse` hook on `Read` refuses a whole read of a text file over 400 lines and points Claude at a search and a sliced read instead; a read with an explicit `offset` or `limit` passes, as do subagents' reads and reads of images, PDFs and notebooks. Both thresholds are flags in the hook command, and both hooks fail open. |

<details>
<summary><b>What the reviewers check</b></summary>

`diff-reviewer` works through its checklist in order of how often each kind of
defect has slipped through in practice. It starts with stale docs, edge cases,
unwired features and missed sibling paths. Those include per-row I/O inside a loop,
reads or fetches with no limit, and readers broken by a changed flag, output
column, file format or JSON shape. Then it checks spec coverage and code or tests
overfitted to the request's examples. After that it looks for tests that cannot
fail, pass only locally, mock the repository's own modules or leave an entry-point
change without an integration test, and for checks the change weakens unasked:
deleted tests or asserts, loosened ruff, pyright, pytest or coverage config, or a
skip added to an existing test. Finally it looks at comments and dead code. The
severity of each finding is tied to an input that would actually fail, and each
is tagged with how that input arises: by default, realistically, or only through
a hand edit, a bypass or an input the default run can't produce. That last kind
is always low. Low-severity findings are capped, and risks it couldn't confirm are named rather
than dropped. Defects that predate the change are tagged `[pre-existing]` and left
out of the verdict, which says whether a re-review is needed. A re-review only
checks the earlier findings, their fixes and what those fixes could break, and
adds nothing new below high. `CLAUDE.md` allows one re-review, and a second
only when that one finds a high.

`spec-reviewer` looks at whether the requirements are testable and feasible, at
edge cases (including concurrent workers and the rest of the category the
request's examples came from), at domain rules, which need independent worked
examples, at figures a model would otherwise have to compute, and at data sources
and wiring. It uses the same severity scale and reach tags as `diff-reviewer`, names the
risks it couldn't confirm in the same way, and limits a re-review to the sections
the revision changed. `spec-writing` calls
it before any tests are written, and devgate ignores it, so a spec review never
stands in for a code review.

</details>

<details>
<summary><b>How devgate decides</b></summary>

devgate only judges lines the session wrote itself through Edit and Write calls,
including those made by its subagents. A `PostToolUse` hook on
`Edit|MultiEdit|Write` records them, and without that hook the gate has nothing to
judge. Anything already uncommitted when the session started is left alone, as are
lines written by another session sharing the same checkout, so a session that only
runs commands is never gated. Edits made through the shell, such as `sed -i` or a
code generator, aren't seen at all.

Checks are detected from the repository's own configuration (ruff, pyright, mypy
and pytest, run through `uv` or `poetry` when the project has a lock file), so a
repository without any of them simply runs none. Linters and type checkers only
report on the files the session wrote to, but pytest runs the whole suite, which
means a test that was already failing blocks every turn that touches Python. Only
code and config lines count toward review or call for a `Not verified:` line;
Markdown and other prose don't. After three blocks in a row, devgate lets the turn
end and reports what is still open. Its state lives in `.git/devgate/`.

In the lines the session added to Python files, a `noqa`, `type: ignore` or
`pyright: ignore` must name the rule it silences and give a reason, as in
`# noqa: BLE001 - a broken gate must not wedge the session`. A
`pragma: no cover`, `pragma: no branch` or pytest `skip`, `skipif` or `xfail` must
give a reason. Lines it added to any file, Markdown included, are scanned for
secrets: known key prefixes, PEM private keys, mnemonics of 12, 15, 18, 21 or 24
words, and 64-hex keys on a line that names a key. The public Hardhat and Anvil
development keys and their mnemonic pass. The block names the kind of secret and
the line, never the text, and any line of check output that holds a possible
secret is hidden. A check whose tool isn't installed doesn't fail the turn, but the
report's `Not verified:` line has to name it.

A review covers the change as it stood when `diff-reviewer` was launched, which a
`PostToolUse` hook on `Agent` records against the agent's id. Edits made while a
background review is running therefore still need a review of their own. Without
that hook, a review covers the change as it stands when the reviewer reports back.
While a review is running, the turn may end without a report, and the change is
judged in full once the reviewer returns. A review that never reports stops
counting as running after `review_expiry` seconds.

A file that was already over the size limit doesn't block when a change makes it
longer. If it grows by more than `size_growth` lines (20 by default), it goes on a
split backlog in `.git/devgate/oversized.json`, which is shown at the start of
every session until the file has been split back under the limit.

A new code module that takes its package past `max_modules` (15 by default;
`__init__` files and test files don't count) blocks, with a request to group
related modules into a subpackage. A package that was already past the limit
doesn't block: the review request asks `diff-reviewer` whether the new module
belongs in a subpackage, and the end-of-turn notice names the package.

</details>

<details>
<summary><b>Configuring devgate</b></summary>

Each repository can override the defaults in `.claude/devgate.toml`:

```toml
enabled = true            # false turns the gate off for this repo
review_threshold = 200    # unreviewed added lines before diff-reviewer is required
review_expiry = 3600      # seconds before a review that never reported counts as abandoned
review_suffixes = ['.py', '.ts', '.md']   # files whose added lines count; Markdown is out by default
max_lines = 400           # file-size limit for code files
size_growth = 20          # lines an already-oversized file may grow before it joins the split backlog
max_modules = 15         # code modules a package may hold before a new one blocks
size_exempt = ['legacy/*']   # globs the size and module limits skip; replaces the default (test files, Markdown)
extra_banned = ['\bTicket-\d+\b']   # more comment patterns to reject

[[checks]]                # replaces detection; {py} expands to the changed Python files
name = "lint"
cmd = "npm run lint"
```

</details>

## Installing

The repository is laid out like a `.claude/` directory, so each part maps directly
onto its destination:

```text
CLAUDE.md               → ~/.claude/CLAUDE.md
skills/<name>/SKILL.md  → ~/.claude/skills/<name>/SKILL.md
agents/*.md             → ~/.claude/agents/
hooks/                  → ~/.claude/hooks/
settings.example.json   → merge into ~/.claude/settings.json
```

Copy what you need into `~/.claude/` to use it in every project, or into a
project's own `.claude/` to use it there only:

```bash
# Skills only
cp -R skills ~/.claude/

# Everything, including the quality gate
cp -R skills agents hooks ~/.claude/
cp -n CLAUDE.md ~/.claude/CLAUDE.md   # -n keeps an existing one; merge by hand instead
```

`cp -R` merges into existing directories and overwrites files with the same name.
The quality gate and the context hooks also need the `hooks` block from
[`settings.example.json`](settings.example.json) merged into
`~/.claude/settings.json`; add its entries to any event lists you already have
rather than replacing them. Repeat that merge after each update, because a missing
entry quietly switches off part of the gate. Agents load when a session starts, so
start a new one afterwards.

### Recommended: rtk

[rtk](https://github.com/rtk-ai/rtk) filters the output of shell commands (test
runs, `git`, linters, searches) before it reaches Claude. It is optional; nothing
here depends on it. It covers the Bash tool only: Read, Grep and Glob pass through
untouched, and the context hooks above are what cover Read.

```bash
brew install rtk
rtk init -g --hook-only --auto-patch
```

`rtk init -g` adds this entry to the `PreToolUse` list in `~/.claude/settings.json`:

```json
{ "matcher": "Bash", "hooks": [{ "type": "command", "command": "rtk hook claude" }] }
```

Without `--hook-only` it also writes `~/.claude/RTK.md` and adds an `@RTK.md` line
to `~/.claude/CLAUDE.md`, which teaches Claude rtk's own commands but edits the
working agreement this repository installs. Without `--auto-patch` it asks before
editing `settings.json` and, given no answer, only prints the entry to add by hand.
Restart Claude Code afterwards.

When a filter drops lines, the output carries a hint such as
`[+7 hidden: rtk recall e264d2dc8b48]`. `rtk recall <hash>` returns what was
dropped (`--full` for the whole output), and `rtk proxy <command>` runs a command
without filtering. Telemetry is off by default and sends nothing until you run
`rtk telemetry enable`.

### Requirements

The quality gate and the context hooks need `python3` 3.12 or newer on your
`PATH`. You can run their tests with
`cd hooks && uv run --no-project --with pytest pytest`.

`security-advisories` also needs [`osv-scanner`](https://github.com/google/osv-scanner)
(`brew install osv-scanner`) and `python3` 3.12 or newer. Its tests run with
`cd skills/security-advisories/scripts && uv run --no-project --with pytest pytest`.

The root `CLAUDE.md` applies to sessions working in this repository as well.
The repository's own suite, a routing eval over the skill descriptions and a lint
of the skill, agent and hook files, runs offline from the root with
`uv run --no-project --with pytest pytest`; [`evals/README.md`](evals/README.md)
explains how to add a case.

## License

[MIT](LICENSE) © Orionics Ltd
