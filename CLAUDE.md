# Working agreement

## Ask or check, don't guess

When a choice could reasonably go more than one way, or an assumption about a library, API or data is unverified, ask or check it. Never ship a plausible guess (see `clarify-first`).

## Done means verified

- Before reporting code work as done: lint, type-check and test with the repo's own tools, then exercise the change through its real entry point (`--help`, a dry run, the command on a fixture or recorded responses). Passing unit tests is not the same as wired in.
- Verification never costs money: no paid model or API calls, cloud jobs or on-chain transactions. Use mocks, fixtures, recorded responses or a dry-run mode; if none exists and only a paid run would prove it, say so under `Not verified:` and leave the decision to the user.
- When you change a name, flag, behaviour or file, grep docs, skills, prompts and specs for the old one and update them in the same change.
- When you fix one path, find its siblings (same pattern, same switch, same schema) and fix or rule out each.
- Order the work: implement → lint, type-check, test → the `diff-reviewer` agent once per unit of work (the Stop hook says when) → fix what it confirms → then any expensive end-to-end verification (rebuilds, re-measurements, live runs) once, last. A re-review gets the earlier findings and the files changed since, not the whole diff.
- End every report that changed code with: the commands run and their results, the requirements covered, and a final `Not verified:` line naming what was not checked (`Not verified: nothing` if so).

## Code

- Production quality: code a senior reviewer approves without comments. Match the surrounding idiom.
- Comments state what the code cannot: a reason, a constraint, a gotcha. Never history ("now", "previously"), never plans, phases, work packages, specs sections, reviews or this conversation. No section banners. When in doubt, delete the comment.
- Files stay under ~400 lines; split a module along its seams before it crosses that. A new concept gets its own module in the right package, not a growing script.
- Reuse before adding; the smallest diff that does the job; no dead code, no unused parameters, no magic numbers.
- Functional core, imperative shell: pure functions over immutable data for logic; I/O at the edges. Details in the `coding-standards` skill.

## Specs

Write specs with the `spec-writing` skill: every requirement has an acceptance test, and the tests are written before the implementation.
