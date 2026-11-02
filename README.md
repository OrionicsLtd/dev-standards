# dev-standards

Orionics Ltd's engineering standards, packaged for [Claude Code](https://claude.com/claude-code).
Skills encode reusable working practices (coding standards, context hygiene,
dependency safety, clarifying ambiguity, writing specs, keeping docs and
CLAUDE.md files current, and handling security advisories) that Claude loads automatically when a task matches their
description. Alongside them, a quality gate (hooks, a reviewer agent and a
user-level `CLAUDE.md`) holds work to those practices before Claude reports it
as done.

## What is a skill?

A skill is a directory containing a `SKILL.md` file with YAML frontmatter
(`name` and `description`) followed by guidance in Markdown. Claude reads the
`description` to decide when the skill is relevant and applies the guidance
while it works. See the
[skills documentation](https://docs.claude.com/en/docs/claude-code/skills) for
details.

## Skills in this repo

| Skill | Use it when |
| --- | --- |
| [`clarify-first`](skills/clarify-first/SKILL.md) | A task is unclear, a decision could go multiple ways, or you'd otherwise fill a gap with a guess. Surface and resolve ambiguity instead of shipping a plausible-but-wrong interpretation. |
| [`coding-standards`](skills/coding-standards/SKILL.md) | Writing or editing code, adding a module, or reviewing structure. Keep changes small, well-named, type-hinted, and consistent with the surrounding code; functional core, imperative shell. |
| [`dependency-safety`](skills/dependency-safety/SKILL.md) | A change touches `pyproject.toml`, a lock file, or a Dockerfile. Only touch a dependency when necessary and make the smallest reviewable change. |
| [`docs-maintenance`](skills/docs-maintenance/SKILL.md) | A change alters behaviour a doc describes, a spec or plan is finished or superseded, or docs need tidying. One index, status at the top of each spec, deviations folded back into the requirements, and a check against the code before trusting a doc. |
| [`lean-context`](skills/lean-context/SKILL.md) | Exploring, understanding, or debugging a codebase. Scout with search, read only the slices you need, and keep the context window lean. |
| [`security-advisories`](skills/security-advisories/SKILL.md) | Checking a repo, its runtimes or this machine for known vulnerabilities, triaging security news against what is actually used, and fixing with the smallest upgrade that contains the fix. Uses only free live sources (OSV via `osv-scanner`, CISA's exploited-vulnerability catalog, EPSS, release indexes). |
| [`spec-writing`](skills/spec-writing/SKILL.md) | Writing a spec or design doc, or starting work big enough to need one. Numbered requirements, each with an acceptance test written before the implementation, the domain rules and data sources the change depends on, and the wiring and docs it must touch. The spec is reviewed before its tests are written. |
| [`writing-claude-md`](skills/writing-claude-md/SKILL.md) | Creating, editing or trimming a CLAUDE.md, AGENTS.md or `.claude/rules/` file, or a correction has come up twice. What belongs in each file versus a skill, hook or setting, and how to keep it short and current. |

## Quality gate

Instructions alone drift over a long session; these pieces check the work instead.

| Piece | What it does |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | Always-loaded working agreement: what "done" means, comment and module-size rules, and the report format (ending in a `Not verified:` line). |
| [`agents/diff-reviewer.md`](agents/diff-reviewer.md) | Read-only agent that reviews the uncommitted diff without the session's context, against the user's request and any spec. Its checklist is ordered by how often each defect slipped through in practice: stale docs, edge cases, unwired features and missed sibling paths, spec coverage, tests that cannot fail or pass only locally, comments, dead code. Severity is anchored to a nameable failing input, lows are capped, unconfirmed risks are named rather than dropped, and each review ends with a verdict saying whether a re-review is needed. Specs go to `spec-reviewer` instead. Runs on Haiku at high effort to keep reviews cheap; a re-review checks the earlier findings and only the files changed since, and adds no new lows. |
| [`agents/spec-reviewer.md`](agents/spec-reviewer.md) | Read-only agent that reviews a spec before it is built, against the user's request and the code it will change: testable requirements, feasibility, edge cases including concurrent workers, domain rules with independent worked examples, figures a model would have to compute, data sources, wiring. Same severity, unconfirmed-risk and verdict format as `diff-reviewer`. Runs on Sonnet, since design gaps are where Haiku reviews were weakest. `spec-writing` calls it before tests are written; the Stop hook ignores it, so a spec review never counts as a code review. |
| [`hooks/devgate`](hooks/devgate) | `Stop` hook that blocks the end of a turn while the repo's own checks fail, comments use planning or conversation wording, a change pushes a file past 400 lines, a large change has not been through `diff-reviewer`, or the report lacks its `Not verified:` line. |

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
`PostToolUse` hook on `Agent` records it, keyed by the agent's id), so edits made while
a background review runs still need one; without that hook a review counts for the
change as it stands when the reviewer reports. While a review is running the turn may end without a
report; the change is judged in full once the reviewer is back. A review that never
reports stops counting as running after `review_expiry` seconds.

A file already over the limit that a change grows further does not block: it goes on
a split backlog (`.git/devgate/oversized.json`), which every session start shows until
the file is split back under the limit.

Override per repository in `.claude/devgate.toml`:

```toml
enabled = true            # false turns the gate off for this repo
review_threshold = 200    # unreviewed added lines before diff-reviewer is required
review_expiry = 3600      # seconds before a review that never reported counts as abandoned
review_suffixes = ['.py', '.ts', '.md']   # files whose added lines count; Markdown is out by default
max_lines = 400           # file-size limit for code files
extra_banned = ['\bTicket-\d+\b']   # more comment patterns to reject

[[checks]]                # replaces detection; {py} expands to the changed Python files
name = "lint"
cmd = "npm run lint"
```

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
[`settings.example.json`](settings.example.json) into `~/.claude/settings.json` (again
after each update, since a missing entry silently disables part of the gate), and
start a new session (agents load at session start). The gate needs `python3` 3.12
or newer on `PATH`; run its tests with
`cd hooks && uv run --no-project --with pytest pytest`.

`security-advisories` needs [`osv-scanner`](https://github.com/google/osv-scanner)
(`brew install osv-scanner`) and `python3` 3.12 or newer; run its tests with
`cd skills/security-advisories/scripts && uv run --no-project --with pytest pytest`.

The root `CLAUDE.md` also applies to sessions working in this repository.

## License

[MIT](LICENSE) © Orionics Ltd
