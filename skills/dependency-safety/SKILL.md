---
name: dependency-safety
description: >-
  Guardrails for changing dependencies. Use this WHENEVER a change touches
  pyproject.toml, lock files, adds/upgrades/pins a package, or
  edits a Dockerfile or its base image: only touch a dependency when genuinely necessary,
  make the smallest reviewable change, and never bump versions or regenerate a lockfile casually.
---

# Dependency safety

**Changes are minimal — only what is necessary.**

## Default to no change

Before touching a dependency, ask: **is this necessary?** Only add, upgrade, or
pin one for a concrete reason — a bug you need fixed, a security advisory, a
feature the task actually requires. If the task works with what's already there,
change nothing.

- **Don't add a package for something small** — prefer the standard library or an
  existing dependency over a new package for a few lines of functionality.
- **Don't upgrade unrelated packages** — a bump that isn't part of the task is
  scope creep and a review burden. Leave it out.
- **Don't regenerate the lockfile casually** — `uv lock`/`uv sync` (or `npm install`,
  `poetry update`, `cargo update`) can silently re-resolve dozens of
  transitive deps. Regenerate only when you mean to, then review the diff.

## Review the lockfile diff

After any dependency change, **read the lock diff** and confirm only what you
intended moved:

- If a package you didn't touch changed version, stop and find out why — an
  accidental transitive bump is the most common silent regression.
- Scrutinize **compiled / C-extension packages** (numpy, pandas, pyarrow,
  cryptography, grpcio, pillow, …). They carry native ABI constraints and
  are the most likely to break a runtime that looked fine at build time.
- If a stray command rewrote the lock, restore it (`git checkout <ref> -- <lock>`)
  rather than committing an unintended re-resolve.

## Pin with intent

- Prefer an explicit, minimal version constraint over "latest." Know what a change
  to a bound actually allows before you widen or bump it.
- If a resolver setting controls reproducibility (e.g. uv's `exclude-newer`), keep
  it valid for the tool version in use — a value an older tool can't parse may be
  silently ignored, letting the resolver pull the newest of everything.

## When debugging, change one thing at a time

If a dependency/runtime issue is already burning, resist shotgun fixes (bump the
package *and* swap the base *and* re-lock at once). Change one variable, verify,
then the next — otherwise you won't know what actually fixed it, and you risk
trading one silent drift for another.
