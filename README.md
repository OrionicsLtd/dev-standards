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
| `Write a spec for adding a --dry-run flag to the export command.` | `spec-writing` | It writes numbered requirements, gives each one an acceptance test, and has `spec-reviewer` check the spec before any test is written. |
| `Write tests for the retry logic in client.py.` | `testing` | It unit-tests the pure logic and adds an integration test through the real entry point, faking only the I/O edge (network, clock, randomness). |
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
| [`clarify-first`](skills/clarify-first/SKILL.md) | When a task is unclear or could reasonably go more than one way, Claude asks or checks instead of shipping a plausible guess. It also treats examples in a request as a sample of a wider category unless they are clearly the full list. |
| [`coding-standards`](skills/coding-standards/SKILL.md) | Whenever Claude writes or edits code, it keeps changes small, well named and type-hinted, matches the code around them, and puts logic in pure functions with I/O kept at the edges. |
| [`dependency-safety`](skills/dependency-safety/SKILL.md) | When a change reaches `pyproject.toml`, a lock file or a Dockerfile, Claude touches a dependency only if it has to and keeps the change small enough to review. |
| [`docs-maintenance`](skills/docs-maintenance/SKILL.md) | When a change alters behaviour that a doc describes, or a spec is finished or superseded, Claude keeps the docs true. Specs share one index and carry their status at the top, deviations are folded back into the requirements, and a doc is checked against the code before anyone relies on it. |
| [`lean-context`](skills/lean-context/SKILL.md) | While exploring or debugging a codebase, Claude searches before it reads, opens only the parts of files it needs, and keeps its context window small. |
| [`security-advisories`](skills/security-advisories/SKILL.md) | When you ask about known vulnerabilities or a piece of security news, Claude checks it against what is actually in use and fixes it with the smallest upgrade that contains the fix. It works from free live sources such as OSV, GHSA, NVD, CISA's catalog of exploited vulnerabilities, EPSS and vendor release indexes. |
| [`spec-writing`](skills/spec-writing/SKILL.md) | When you ask for a spec or design doc, or start work big enough to need one, every requirement is numbered and has an acceptance test written before the implementation. The spec also records the domain rules and data sources the change depends on, and the wiring and docs it touches. |
| [`testing`](skills/testing/SKILL.md) | When Claude writes, changes or reviews tests, unit tests cover the pure core and integration tests go through the real entry point, with fakes only at the I/O edge and nothing running against live services. |
| [`writing-claude-md`](skills/writing-claude-md/SKILL.md) | When you create, edit, trim or review a CLAUDE.md, AGENTS.md or `.claude/rules/` file, or say "from now on…", or the same correction comes up twice, Claude works out what belongs in each file rather than in a skill, hook or setting, and keeps the files short and current. |

## Quality gate

Instructions on their own tend to drift over a long session, so the quality gate
checks the work itself.

| Piece | What it does |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | The working agreement Claude loads in every session. It defines what "done" means, sets the rules for comments and module size, and fixes the report format, which ends with a `Not verified:` line. |
| [`agents/diff-reviewer.md`](agents/diff-reviewer.md) | A read-only agent that reviews the uncommitted diff against the user's request and any spec, without seeing the session's context. It runs on Haiku at high effort, which keeps reviews cheap. |
| [`agents/spec-reviewer.md`](agents/spec-reviewer.md) | A read-only agent that reviews a spec against the request and the code it will change, before anything is built. It runs on Sonnet, because design gaps were where Haiku's reviews were weakest. |
| [`hooks/devgate`](hooks/devgate) | A `Stop` hook that holds a turn open while the repository's own checks fail. It also blocks comments written in planning or conversation wording, non-test files pushed past 400 lines, large changes that haven't been through `diff-reviewer`, and reports that lack their `Not verified:` line. |

<details>
<summary><b>What the reviewers check</b></summary>

`diff-reviewer` works through its checklist in order of how often each kind of
defect has slipped through in practice. It starts with stale docs, edge cases,
unwired features and missed sibling paths, then checks spec coverage and code or
tests overfitted to the request's examples. After that it looks for tests that
cannot fail, pass only locally, mock the repository's own modules or leave an
entry-point change without an integration test, and finally at comments and dead
code. The severity of each finding is tied to an input that would actually fail,
low-severity findings are capped, and risks it couldn't confirm are named rather
than dropped. Every review ends with a verdict saying whether a re-review is
needed. A re-review only checks the earlier findings and the files changed since,
and adds no new low-severity findings.

`spec-reviewer` looks at whether the requirements are testable and feasible, at
edge cases (including concurrent workers and the rest of the category the
request's examples came from), at domain rules, which need independent worked
examples, at figures a model would otherwise have to compute, and at data sources
and wiring. It uses the same severity scale as `diff-reviewer` and names the risks
it couldn't confirm in the same way. `spec-writing` calls
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
size_exempt = ['legacy/*']   # globs the size limit skips; replaces the default (test files, Markdown)
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
The quality gate also needs the `hooks` block from
[`settings.example.json`](settings.example.json) merged into
`~/.claude/settings.json`. Repeat that merge after each update, because a missing
entry quietly switches off part of the gate. Agents load when a session starts, so
start a new one afterwards.

### Requirements

The quality gate needs `python3` 3.12 or newer on your `PATH`. You can run its
tests with `cd hooks && uv run --no-project --with pytest pytest`.

`security-advisories` also needs [`osv-scanner`](https://github.com/google/osv-scanner)
(`brew install osv-scanner`) and `python3` 3.12 or newer. Its tests run with
`cd skills/security-advisories/scripts && uv run --no-project --with pytest pytest`.

The root `CLAUDE.md` applies to sessions working in this repository as well.

## License

[MIT](LICENSE) © Orionics Ltd
