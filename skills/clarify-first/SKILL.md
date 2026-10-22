---
name: clarify-first
description: >-
  Use this whenever a task is unclear, a decision could plausibly go multiple
  ways, the codebase has no obvious precedent to follow, or you find yourself
  filling in gaps the user did not specify — vague instructions, missing context,
  multi-option decisions, or unverified assumptions about how a library, API, or
  piece of data actually behaves. The rule: surface and resolve ambiguity (ask, or
  verify) instead of shipping a plausible guess. The most expensive bugs are
  correct-looking code that quietly solves the wrong problem.
---

# Clarify first

The most expensive bugs come from unstated assumptions that turn out wrong — code
that looks correct because it follows *a* plausible interpretation, but solves a
different problem from the one the user actually has. Cheaper to ask one question
than to build the wrong thing convincingly.

## Don't make silent assumptions

When something is genuinely ambiguous, **ask** — don't pick the most likely option
and ship. Watch for it in:

- **Requirements** — "add a filter to the transactions page" — by date? amount?
  category? all of them?
- **Data shape** — what fields does this API actually return? what does the form submit?
- **Approach** — extend an existing endpoint, or add a new one?
- **Scope** — does this also need to touch X, Y, Z, or just the one thing mentioned?

## How to ask

Be brief. Present the realistic options, not every conceivable one, and say which
is cheapest if you know.

- **Bad:** "I'm not sure how to proceed, could you give more details?"
- **Good:** "Before I build this — date filter as (a) single month picker, (b)
  from/to range, or (c) both? The existing component supports range, so (b) is
  cheapest."

Calibrate to reversibility:

- **Small and reversible** — state your assumption and proceed: "I'll name it
  `parse_statement` to match the verb-form of its neighbours; say if you'd prefer
  `StatementParser`."
- **Large or hard to reverse** (DB schema, public API shape, a new dependency,
  file/package structure) — **ask first**, before writing it.

## Verify — don't fabricate

If you don't know how a library works, what a piece of data really looks like, or
how a value is computed — **find out**: run code to check, read the source/docs,
or ask. Don't write code that "should work" resting on an assumption you never
confirmed. A confident guess about external behaviour is exactly what blows up in
production. Saying "I don't know yet, let me verify" is strength, not weakness.

## Don't add behaviour the user didn't ask for

Silent fallback values, automatic retries, hidden defaults, "helpful" extra
features — if the user didn't ask for it, stop and check before adding it. Quiet
behaviour is the worst kind of surprise: it hides the real state, and the failure
surfaces far from the cause (a silent default that masks a misconfiguration until
prod is a classic). Make behaviour explicit, or confirm it's wanted.

## But don't re-ask what's already decided

The point is to avoid silent assumptions, not to interrupt for things already
settled. Before asking, check: **has the user, the project spec, an existing
skill, or the surrounding code already answered this?** If yes, follow it. If a
sensible, conventional default clearly applies and the choice is cheap, take it and
say so. Reserve questions for real forks — consequential, and genuinely unspecified.
