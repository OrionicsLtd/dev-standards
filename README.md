# dev-standards

Orionics Ltd's engineering standards, packaged for [Claude Code](https://claude.com/claude-code).
Skills encode reusable working practices (coding standards, context hygiene,
dependency safety, clarifying ambiguity, writing specs and handling security
advisories) that Claude loads automatically when a task matches their
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
| [`lean-context`](skills/lean-context/SKILL.md) | Exploring, understanding, or debugging a codebase. Scout with search, read only the slices you need, and keep the context window lean. |
| [`security-advisories`](skills/security-advisories/SKILL.md) | Checking a repo, its runtimes or this machine for known vulnerabilities, triaging security news against what is actually used, and fixing with the smallest upgrade that contains the fix. Uses only free live sources (OSV via `osv-scanner`, CISA's exploited-vulnerability catalog, EPSS, release indexes). |
| [`spec-writing`](skills/spec-writing/SKILL.md) | Writing a spec or design doc, or starting work big enough to need one. Numbered requirements, each with an acceptance test written before the implementation, plus the wiring and docs the change must touch. |

## Quality gate

Instructions alone drift over a long session; these pieces check the work instead.

| Piece | What it does |
| --- | --- |
| [`CLAUDE.md`](CLAUDE.md) | Always-loaded working agreement: what "done" means, comment and module-size rules, and the report format (ending in a `Not verified:` line). |
| [`agents/diff-reviewer.md`](agents/diff-reviewer.md) | Read-only agent that reviews the uncommitted diff without the session's context, against the user's request and any spec. Its checklist is ordered by how often each defect slipped through in practice: stale docs, edge cases, unwired features and missed sibling paths, spec coverage, tests, comments, dead code. Runs on Haiku at high effort to keep reviews cheap; a re-review checks the earlier findings and only the files changed since. |
| [`hooks/devgate`](hooks/devgate) | `Stop` hook that blocks the end of a turn while the repo's own checks fail, comments use planning or conversation wording, a change pushes a file past 400 lines, a large change has not been through `diff-reviewer`, or the report lacks its `Not verified:` line. |

devgate only judges lines the session added; changes already uncommitted when the
session started are left alone. Checks are detected from the repo's own config
(ruff, pyright, mypy and pytest, run through `uv`/`poetry` when locked), so a
repository without them simply runs none. After three consecutive blocks it lets
the turn end and reports what is still open. State lives in `.git/devgate/`.

A file already over the limit that a change grows further does not block: it goes on
a split backlog (`.git/devgate/oversized.json`), which every session start shows until
the file is split back under the limit.

Override per repository in `.claude/devgate.toml`:

```toml
enabled = true            # false turns the gate off for this repo
review_threshold = 200    # unreviewed added lines before diff-reviewer is required
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
agents/diff-reviewer.md → ~/.claude/agents/diff-reviewer.md
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
[`settings.example.json`](settings.example.json) into `~/.claude/settings.json`, and
start a new session (agents load at session start). The gate needs `python3` 3.12
or newer on `PATH`; run its tests with
`cd hooks && uv run --no-project --with pytest pytest`.

`security-advisories` needs [`osv-scanner`](https://github.com/google/osv-scanner)
(`brew install osv-scanner`) and `python3` 3.12 or newer; run its tests with
`cd skills/security-advisories/scripts && uv run --no-project --with pytest pytest`.

The root `CLAUDE.md` also applies to sessions working in this repository.

## License

[MIT](LICENSE) © Orionics Ltd
