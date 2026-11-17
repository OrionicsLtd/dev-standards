# Routing evals and repository lint

Status: built

## Goal

Every skill's description is loaded into every session, and Claude picks a skill by
matching the request against those descriptions. Two descriptions that read alike make
that pick a coin toss, and a renamed skill or reviewer leaves dangling references
behind. This suite catches both offline, on every change to this repository: a routing
eval over the descriptions and a lint over the skill, agent and hook files.

## Running

From the repository root:

```bash
uv run --no-project --with pytest pytest
```

```bash
uvx ruff check tests && uvx ruff format --check tests
```

## Adding an eval

Each skill has `evals/<skill>.json`:

```json
{
  "prompts": [
    "A request this skill must rank first for.",
    {"prompt": "A request it should win but does not.", "known_collision": "why"}
  ],
  "negatives": [
    {"prompt": "A nearby request another skill must win.", "winner": "other-skill"}
  ],
  "known_pair_collisions": {"other-skill": "why the two descriptions overlap"}
}
```

Write prompts the way a user would type them, not by copying words from the
description: the eval measures whether the descriptions separate real requests. When a
prompt fails, the descriptions collide: keep the prompt, add `known_collision` with the
reason, and report it. The case then runs as an expected failure, and the suite fails
once the descriptions are fixed so that the marker gets removed.

## Non-goals

- No model calls and no measure of how Claude actually routes: TF-IDF is a lexical proxy
  that flags descriptions sharing vocabulary, not a simulation of the model.
- Does not rewrite descriptions; a failing eval is recorded as a known collision.
- Does not collect the existing suites under `hooks/` or `skills/security-advisories/`;
  they keep their own `pyproject.toml`.
- Does not check agent description length, nor references to single-word skill names
  such as `testing` (indistinguishable from code in backticks).

## Interface

- `pyproject.toml` at the root: `[tool.ruff]` with the rules `hooks/` uses,
  `[tool.pytest.ini_options]` with `testpaths = ["tests"]`, `pythonpath = ["tests"]`.
  devgate reads the root `pyproject.toml`, so the suite runs under its Stop check once
  pytest is reachable (a lock file or `.venv`, or pytest on `PATH`). `hooks/` keeps
  linting under its own, nearer `pyproject.toml`.
- `tests/repo_files.py`: `Doc(name, path, description)`; `parse_frontmatter(text) ->
  dict[str, str] | None` (None without frontmatter); `load_skills(root) -> tuple[Doc, ...]`;
  pure lint checks, each returning a tuple of problem strings (empty when clean).
- `tests/tfidf.py`: `tokenize(text)`, `fit(descriptions) -> Index`,
  `rank(index, prompt) -> tuple[tuple[str, float], ...]`, `routes_to(ranking, skill)`,
  `pair_scores(index) -> tuple[tuple[str, str, float], ...]`, `collides(score, ceiling)`.
- `tests/evalcases.py`: loads and validates `evals/*.json` into cases.
- `tests/test_*.py`: unit tests on fixtures, plus the checks against this repository.

## Requirements

Routing:

- **R1** Tokens are the lowercase runs of `[a-z0-9]` in the text with plurals folded: a
  run over four characters ending in `ies` ends in `y` instead; otherwise a run over three
  characters ending in `s` but not `ss` loses the `s`. A run is dropped when either its raw
  or its folded form is a stopword (so "this" and "needs" both go). Stopwords: a about after all an and any are as at be before but by can could do
  does for from has have how i if in into is it its just me my need of on or our please
  should so than that the their them then there these they this to us use using was we
  what when whenever where which while who will with would you your.
- **R2** Weights are TF-IDF fitted on the skill descriptions only: raw term count times
  `ln((1 + n) / (1 + df)) + 1`, vectors L2-normalised, scores are cosine similarity. A
  prompt's tokens absent from every description are ignored.
- **R3** `rank` orders skills by score descending, then by name.
- **R4** A prompt routes to a skill when that skill ranks first with a score above zero
  and strictly above the second skill's. Every prompt in `evals/<skill>.json` routes to
  `<skill>`; a failure names the prompt and the top three skills with scores.
- **R5** Every negative routes to its `winner` under the rule in R4.
- **R6** No two skill descriptions score 0.35 or more against each other; a failure
  names the pair and score.
- **R7** A case with `known_collision`, and a pair listed in either skill's
  `known_pair_collisions`, runs as a strict expected failure with that reason: the suite
  passes while it fails and fails once it passes.

Eval files:

- **R8** Every skill has an eval file with at least one prompt; every file matching
  `evals/*.json` names an existing skill.
- **R9** An eval file is a JSON object with key `prompts` (a non-empty list whose entries
  are non-empty strings or `{"prompt", "known_collision"}` objects), optional `negatives`
  (a list of `{"prompt", "winner"}` objects, optionally with `known_collision`) and
  optional `known_pair_collisions` (an object mapping another skill to a reason). Invalid
  JSON, any other shape, an unknown key, an empty prompt or reason, a `winner` or pair skill that is
  not a skill, or one equal to the file's own skill raises `ValueError` naming the file and
  the reason.
- **R10** A prompt appears at most once across all prompts and negatives of all eval
  files, the same file included.
- **R11** The eval files hold negatives for these collisions, each meaning "the file of
  the first skill has a negative whose winner is the second": dependency-safety →
  security-advisories and back, testing → spec-writing and back, docs-maintenance →
  spec-writing and back, and coding-standards → every other skill.

Lint:

- **R12** Each `skills/<dir>/SKILL.md` has frontmatter with `name` equal to `<dir>` and a
  non-empty `description`; each `agents/<file>.md` has `name` equal to its file stem. A
  missing file, missing frontmatter or missing key is a problem, not a crash.
- **R13** A skill description is at most 1024 characters.
- **R14** In `skills/**/*.md`, `agents/*.md`, `CLAUDE.md` and `README.md`: every match of
  `skills/([a-z0-9-]+)/` names an existing skill directory, every `agents/([a-z0-9-]+)\.md`
  an existing agent file, and every `` `([a-z0-9]+(?:-[a-z0-9]+)+)` `` is a skill, an
  agent or on the allowlist (`osv-scanner`, `exclude-newer`). A problem names file, line
  and token.
- **R15** The reviewer name agrees: `REVIEWER` in `hooks/devgate/gate.py` (read by
  parsing, not importing), the `name` in `agents/<REVIEWER>.md`, and every `SubagentStop`
  entry in `settings.example.json` whose command runs devgate's `subagent-stop` has a
  `matcher` that, read as a regular expression, fully matches `REVIEWER`; at least one
  such entry exists.

## Acceptance tests

| Req | Test | Level | Input → expected |
|---|---|---|---|
| R1 | `test_tokenize_lowercases_drops_stopwords_and_folds_plurals` | unit | `"Use this WHENEVER a pyproject.toml changes"` → `("pyproject", "toml", "change")`; `"dependencies tests class bus readmes"` → `("dependency", "test", "class", "bus", "readme")` |
| R1 | `test_tokenize_drops_plurals_of_stopwords` | unit | `"It needs retries and uses its cache"` → `("retry", "cache")` |
| R2 | `test_fit_weights_match_hand_computed_idf` | unit | corpus `a: "alpha beta"`, `b: "beta gamma"` → `pair_scores` gives `cos(a, b) = 1 / 2.975332 = 0.336097` (approx 1e-6) |
| R2 | `test_rank_ignores_unknown_words` | unit | prompt `"alpha zeta"` → `a` scores `1.405465 / 1.724915 = 0.814802`, `b` scores 0 |
| R3 | `test_rank_breaks_ties_by_name` | unit | prompt `"beta"` → `a`, `b`, both approx `0.579739` |
| R4 | `test_routes_to_rejects_ties_and_zero_scores` | unit | on that corpus: `"beta"` does not route to `a` (tie); `"zeta"` routes nowhere (all zero); `"alpha"` routes to `a` |
| R4, R7 | `test_prompt_routes_to_its_skill[<skill>: <prompt>]` | integration | every prompt in `evals/` |
| R5, R7 | `test_negative_routes_to_its_winner[<skill>: <prompt>]` | integration | every negative in `evals/` |
| R6, R7 | `test_descriptions_stay_apart[<a>/<b>]` | integration | every pair of this repo's descriptions |
| R6 | `test_pair_scores_rate_identical_descriptions_one_and_disjoint_zero` | unit | `x`, `y` identical and `z` disjoint → `x`/`y` approx 1.0, `x`/`z` and `y`/`z` 0 |
| R6 | `test_collides_at_and_above_the_ceiling` | unit | ceiling 0.35: 0.35 and 0.36 collide; 0.3499 and 0 do not |
| R6 | `test_every_pair_of_skills_is_scored` | integration | this repo: one score per unordered pair of skills |
| R7 | `test_known_collision_marks_case_as_strict_xfail` | unit | a case with `known_collision: "r"` → pytest param with `xfail(strict=True, reason="r")`; without → no marks |
| R8 | `test_eval_coverage_names_missing_and_unknown_skills` | unit | skills `{a, b}`, files `{a, c}` → problems name `b` and `c` |
| R8 | `test_every_skill_has_an_eval_file` | integration | this repo: no problems |
| R9 | `test_load_rejects_malformed_file` (parametrised) | unit | invalid JSON, non-object, missing `prompts`, empty `prompts`, empty prompt, prompt object without `known_collision`, empty reason, unknown key in the file, a prompt or a negative, unknown winner, winner not a string, self winner, unknown or self pair skill → `ValueError` whose message names the file |
| R9 | `test_load_reads_strings_objects_and_negatives` | unit | one of each entry kind → cases with prompt, expected skill and reason |
| R10 | `test_duplicate_prompts_are_reported` | unit | same prompt in two files, twice in one file's prompts, and in one file's prompts and negatives → three problems |
| R10 | `test_eval_prompts_are_unique` | integration | this repo: no problems |
| R11 | `test_required_negatives_are_reported_when_missing` | unit | files lacking one required negative → one problem naming the pair |
| R11 | `test_required_collisions_have_negatives` | integration | this repo: no problems |
| R12 | `test_name_checks_report_mismatch_and_missing_frontmatter` | unit | `skills/x/SKILL.md` with `name: y`; dir with no `SKILL.md`; file without frontmatter; frontmatter without `description`; agent `a.md` with `name: b` → five problems |
| R12 | `test_parse_frontmatter_reads_folded_and_plain_values` | unit | `>-` block over two lines → one space-joined string; plain `key: value` |
| R13 | `test_long_descriptions_are_reported` | unit | 1024 chars passes, 1025 fails |
| R14 | `test_dead_references_are_reported` | unit | fixture repo with `` `ghost-skill` ``, `skills/ghost/`, `agents/ghost.md`, `` `osv-scanner` ``, `` `testing` ``, `skills/<name>/` → three problems, each with file and line |
| R12–R14 | `test_repository_is_clean[<check>]` | integration | this repo: no problems |
| R15 | `test_reviewer_name_mismatch_is_reported` (parametrised) | unit | gate and agent disagree; matcher does not match; matcher is a prefix; matcher is an invalid regex; no entry runs `subagent-stop` → one problem each; `test_reviewer_matcher_alternation_is_accepted`: `rev\|other` → no problem |
| R15 | `test_reviewer_name_agrees` | integration | this repo: no problems |

## Edge cases

- *(user)* dependency-safety vs security-advisories, testing vs spec-writing,
  coding-standards vs the rest → R11.
- *(added)* docs-maintenance vs spec-writing, the closest pair → R11.
- *(added)* prompt with no known token → R4 (routes nowhere).
- *(added)* tie at the top → R4, R5.
- *(added)* known collision fixed by a description change → R7 (strict xfail fails).
- *(added)* duplicate prompt across files, within a file, between prompts and negatives
  → R10.
- *(added)* eval file for a skill that no longer exists, skill without an eval file → R8.
- *(added)* invalid JSON → R9.
- *(added)* skill directory without `SKILL.md`, frontmatter without `description` → R12.
- *(added)* description exactly 1024 → R13 (passes).
- *(added)* placeholder paths such as `skills/<name>/` → R14 (not matched).
- *(added)* regex alternation in the `SubagentStop` matcher → R15.
- Out of scope: YAML features beyond `key: value` and `>-`/`>` folded blocks (none are
  used); references inside code fences are checked like any other line.

## Data and domain

- *Collision ceiling 0.35*: chosen with the user, with headroom over every pair except
  docs-maintenance / spec-writing, a known collision. Scores move whenever any
  description changes, since IDF is fitted on all of them; `pair_scores` in
  `tests/tfidf.py` gives the current ones. Applied in R6 only.
- *Plural folding*: chosen with the user over exact word forms, which kept
  docs-maintenance / spec-writing under the ceiling but failed prompts on surface forms
  ("README" against "READMEs").
- *1024 characters*: the platform's limit on a skill description. Applied in R13 only.
- *IDF formula*: the smoothed form `ln((1 + n) / (1 + df)) + 1` (as in scikit-learn's
  default), implemented in the standard library; no new dependency.
- *Sources*: all inputs are committed files in this repository; tests of the checks
  themselves use `tmp_path` fixtures.

## Wiring

- `pyproject.toml` (new, root) — the runner devgate detects.
- `evals/*.json`, `evals/README.md` (this file), `tests/` (new).
- Left for the final sweep (TODO section 10): the README's Requirements section should
  name the new suite's command.

## Open questions

None.
