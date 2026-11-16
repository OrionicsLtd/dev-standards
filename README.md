<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="assets/orionics-lockupA-paper-blue-on-ink.png">
    <img src="assets/orionics-lockupA-ink-blue.png" alt="Orionics" width="320">
  </picture>
</p>

<h1 align="center">dev-standards</h1>

<p align="center">
  Engineering standards for <a href="https://claude.com/claude-code">Claude Code</a>:
  skills that shape how Claude works, and a quality gate that checks the result.
</p>

<p align="center">
  <a href="#try-it">Try it</a> ·
  <a href="#skills">Skills</a> ·
  <a href="#quality-gate">Quality gate</a> ·
  <a href="#installing">Installing</a>
</p>

---

Orionics Ltd's working practices, packaged so Claude loads them on its own:
nine **skills** cover coding standards, testing, context hygiene, dependency
safety, clarifying ambiguity, specs, docs, CLAUDE.md files and security
advisories. A **quality gate** (hooks, two reviewer agents and a
user-level `CLAUDE.md`) holds the work to those practices before Claude reports
it as done.

## Quick start

```bash
git clone https://github.com/OrionicsLtd/dev-standards.git && cd dev-standards
cp -R skills ~/.claude/
```

That installs the skills for every project. To add the quality gate too, see
[Installing](#installing).

## Try it

A skill does nothing until you ask Claude something it covers. Paste one of these
into a session:

| Prompt | Skill that loads | What changes |
| --- | --- | --- |
| `Add caching to the API.` | `clarify-first` | Claude asks about the open scope (which endpoints, how entries are invalidated) and states the small assumptions it makes, instead of guessing. |
| `Write a spec for adding a --dry-run flag to the export command.` | `spec-writing` | Numbered requirements, each with an acceptance test, reviewed by `spec-reviewer` before any test is written. |
| `Write tests for the retry logic in client.py.` | `testing` | Unit tests on the pure logic, an integration test through the real entry point, fakes only at the I/O edge (network, clock, randomness). |
| `Upgrade requests to get rid of the warning in CI.` | `dependency-safety` | The smallest pin change that fixes it, without regenerating the whole lock file. |
| `Is anything here affected by this week's Node.js security release?` | `security-advisories` | Checks what the repo and machine actually run against live advisory data, then proposes the smallest fixing upgrade. |
| `From now on, always run make lint before committing.` | `writing-claude-md` | Decides whether that belongs in CLAUDE.md, a hook or a setting, and writes it there. |

With the quality gate installed, a turn can't end on work that skips the
standards. This is devgate's real reply to a session that left a planning note in
a comment:

```text
Fix these before finishing:

Style rules (see CLAUDE.md):
src/export.py:6: comment wording `Phase 2: switch to streaming once the new writer lands`
```

Claude fixes it and tries again. The turn ends once the checks pass, a large
change has been through `diff-reviewer` and the report ends with a `Not verified:`
line; after three blocks in a row it ends anyway and lists what is still open.

## Skills

A skill is a directory holding a `SKILL.md`: YAML frontmatter (`name` and
`description`) followed by guidance in Markdown. Claude reads the `description` to
decide when the skill is relevant and applies the guidance while it works
([how skills work](https://docs.claude.com/en/docs/claude-code/skills)).

| Skill | Use it when |
| --- | --- |
| [`clarify-first`](skills/clarify-first/SKILL.md) | A task is unclear or could go more than one way. Resolve the ambiguity instead of shipping a plausible guess; treat examples in a request as a sample of a category, not the full list. |
| [`coding-standards`](skills/coding-standards/SKILL.md) | Writing or editing code. Small, well-named, type-hinted changes that match the surrounding code; functional core, imperative shell. |
| [`dependency-safety`](skills/dependency-safety/SKILL.md) | A change touches `pyproject.toml`, a lock file or a Dockerfile. Touch a dependency only when necessary, in the smallest reviewable change. |
| [`docs-maintenance`](skills/docs-maintenance/SKILL.md) | A change alters behaviour a doc describes, or a spec is finished or superseded. One index, status on every spec, and a check against the code before trusting a doc. |
| [`lean-context`](skills/lean-context/SKILL.md) | Exploring or debugging a codebase. Search first, read only the slices you need, keep the context window lean. |
| [`security-advisories`](skills/security-advisories/SKILL.md) | Checking for known vulnerabilities or triaging security news. Uses free live sources (OSV, CISA's exploited-vulnerability catalog, EPSS, release indexes) and fixes with the smallest upgrade that contains the fix. |
| [`spec-writing`](skills/spec-writing/SKILL.md) | Writing a spec, or starting work big enough to need one. Numbered requirements, each with an acceptance test written before the implementation, plus the domain rules, data sources, wiring and docs the change touches. |
| [`testing`](skills/testing/SKILL.md) | Writing, changing or reviewing tests. Unit tests on the pure core, integration tests through the real entry point, fakes only at the I/O edge, no tests against live services. |
| [`writing-claude-md`](skills/writing-claude-md/SKILL.md) | Creating or trimming a CLAUDE.md, AGENTS.md or `.claude/rules/` file, or a correction has come up twice. What belongs in each file versus a skill, hook or setting. |

## Quality gate

Instructions alone drift over a long session; these pieces check the work instead.

| Piece | What it does |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | Always-loaded working agreement: what "done" means, comment and module-size rules, and the report format ending in a `Not verified:` line. |
| [`agents/diff-reviewer.md`](agents/diff-reviewer.md) | Read-only agent that reviews the uncommitted diff without the session's context, against the user's request and any spec. Runs on Haiku at high effort to keep reviews cheap. |
| [`agents/spec-reviewer.md`](agents/spec-reviewer.md) | Read-only agent that reviews a spec before it is built, against the request and the code it will change. Runs on Sonnet, since design gaps are where Haiku was weakest. |
| [`hooks/devgate`](hooks/devgate) | `Stop` hook that blocks the end of a turn while the repo's checks fail, comments use planning or conversation wording, a non-test file passes 400 lines, a large change hasn't been through `diff-reviewer`, or the report lacks its `Not verified:` line. |

<details>
<summary><b>What the reviewers check</b></summary>

`diff-reviewer`'s checklist is ordered by how often each defect slipped through in
practice: stale docs, edge cases, unwired features and missed sibling paths, spec
coverage, code or tests overfitted to the request's examples, tests that cannot
fail, pass only locally, mock the repo's own modules or leave an entry-point
change without an integration test, comments, dead code. Severity is anchored to a
nameable failing input, lows are capped, unconfirmed risks are named rather than
dropped, and each review ends with a verdict saying whether a re-review is needed.
A re-review checks the earlier findings and only the files changed since, and adds
no new lows.

`spec-reviewer` checks testable requirements, feasibility, edge cases including
concurrent workers and the rest of the category the request's examples came from,
domain rules with independent worked examples, figures a model would have to
compute, data sources and wiring, in the same severity, unconfirmed-risk and
verdict format. `spec-writing` calls it before tests are written; devgate ignores
it, so a spec review never counts as a code review.

</details>

<details>
<summary><b>How devgate decides</b></summary>

devgate's style rules and review only judge lines the session wrote with its own
Edit and Write calls (a `PostToolUse` hook on `Edit|MultiEdit|Write` records them,
its subagents' included; without that hook the gate judges nothing). Changes
already uncommitted when the session started, and lines another session sharing
the checkout writes, are left alone, so a session that only runs commands and
edits no code is never gated. Edits made through the shell (`sed -i`, generators)
are not seen. Linters and type checkers report only on the files the session wrote
to, but pytest runs the whole suite, so a test that already fails blocks every
turn that touches Python. Checks are detected from the repo's own config (ruff,
pyright, mypy and pytest, run through `uv`/`poetry` when locked), so a repository
without them simply runs none. Only code and config lines count toward review or
need a `Not verified:` line; Markdown and other prose don't. After three
consecutive blocks it lets the turn end and reports what is still open. State
lives in `.git/devgate/`.

A review counts for the change as it stood when `diff-reviewer` was launched (a
`PostToolUse` hook on `Agent` records it, keyed by the agent's id), so edits made
while a background review runs still need one; without that hook a review counts
for the change as it stands when the reviewer reports. While a review is running
the turn may end without a report; the change is judged in full once the reviewer
is back. A review that never reports stops counting as running after
`review_expiry` seconds.

A file already over the limit that a change grows further does not block: it goes
on a split backlog (`.git/devgate/oversized.json`), which every session start
shows until the file is split back under the limit.

</details>

<details>
<summary><b>Configuring devgate</b></summary>

Override per repository in `.claude/devgate.toml`:

```toml
enabled = true            # false turns the gate off for this repo
review_threshold = 200    # unreviewed added lines before diff-reviewer is required
review_expiry = 3600      # seconds before a review that never reported counts as abandoned
review_suffixes = ['.py', '.ts', '.md']   # files whose added lines count; Markdown is out by default
max_lines = 400           # file-size limit for code files
size_exempt = ['legacy/*']   # globs the size limit skips; replaces the default (test files, Markdown)
extra_banned = ['\bTicket-\d+\b']   # more comment patterns to reject

[[checks]]                # replaces detection; {py} expands to the changed Python files
name = "lint"
cmd = "npm run lint"
```

</details>

## Installing

The repository mirrors the layout of a `.claude/` directory:

```text
CLAUDE.md               → ~/.claude/CLAUDE.md
skills/<name>/SKILL.md  → ~/.claude/skills/<name>/SKILL.md
agents/*.md             → ~/.claude/agents/
hooks/                  → ~/.claude/hooks/
settings.example.json   → merge into ~/.claude/settings.json
```

Copy what you need into your user-level `~/.claude/` (every project) or a
project's `.claude/` (that project only):

```bash
# Skills only
cp -R skills ~/.claude/

# Everything, including the quality gate
cp -R skills agents hooks ~/.claude/
cp -n CLAUDE.md ~/.claude/CLAUDE.md   # -n keeps an existing one; merge by hand instead
```

`cp -R` merges into existing directories and overwrites same-named files. For the
quality gate, also merge the `hooks` block of
[`settings.example.json`](settings.example.json) into `~/.claude/settings.json`
(again after each update, since a missing entry silently disables part of the
gate), and start a new session (agents load at session start).

### Requirements

- The gate needs `python3` 3.12 or newer on `PATH`. Run its tests with
  `cd hooks && uv run --no-project --with pytest pytest`.
- `security-advisories` needs [`osv-scanner`](https://github.com/google/osv-scanner)
  (`brew install osv-scanner`) and `python3` 3.12 or newer. Run its tests with
  `cd skills/security-advisories/scripts && uv run --no-project --with pytest pytest`.

The root `CLAUDE.md` also applies to sessions working in this repository.

## License

[MIT](LICENSE) © Orionics Ltd
