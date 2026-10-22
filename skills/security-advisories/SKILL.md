---
name: security-advisories
description: >-
  Check a repository, its runtimes and this machine for known vulnerabilities,
  triage "hot" security news (a CVE, a vendor security release, a compromised
  package, a list of products in the news) against what is actually used, and
  fix them with the smallest upgrade that contains the fix. Use whenever the user
  asks about vulnerabilities, CVEs, advisories, security releases, dependency
  audits, compromised or malicious packages, or whether something in the news
  affects them — and before any dependency change made for security reasons.
---

# Security advisories

Your knowledge stops at your training cutoff; advisories from last week are not
in it. Every claim about a vulnerability — that it exists, what it affects, what
fixes it — comes from a live source fetched now. Your job is matching, judging
reachability and making the fix. All sources here are free; never use a paid one.

## 1. Scan

```bash
python3 -I ~/.claude/skills/security-advisories/scripts/run_advisories.py scan <repo>
python3 -I ~/.claude/skills/security-advisories/scripts/run_advisories.py hot --days 30
```

`scan` runs `osv-scanner` over every lockfile git does not ignore (PyPI, npm,
pnpm, yarn, Go, Cargo and more, including OpenSSF malicious-package records),
marks advisories CISA lists as exploited in the wild, adds EPSS exploitation
probabilities, and checks Node, Python and Go — installed here or pinned in
`.nvmrc`, `.python-version` and Dockerfiles — against their release lines.
`hot` lists what CISA added to its exploited catalog recently. If `osv-scanner`
is missing, ask the user to `brew install osv-scanner`.

Not covered by the scan, so check by hand when relevant: Foundry/Soldeer
libraries (read the version from `foundry.lock`, `soldeer.lock` or
`lib/<name>/package.json` and query OSV for the matching npm package, e.g.
`@openzeppelin/contracts`), vendored code, CI images and pinned CI actions.

## 2. Triage news the user brings

For each item (a pasted list, a vendor page, a CVE id):

1. **Find out what it is from a primary source** — the vendor advisory, GHSA, NVD
   or OSV entry. Some sites can't be fetched (x.com, for one); ask the user to
   paste the text instead of guessing.
2. **Match it against what is used**, in three places:
   - the repo: `git grep -il <name> -- '*lock*' pyproject.toml package.json go.mod Cargo.toml`
   - this machine: `command -v <tool>`, `brew list --versions <tool>`, the version manager in use
   - services: CI config, deploy config and docs naming the service (GitLab, a host, an API)
3. **Classify** each as affects the repo, affects this machine, affects a service
   the user runs or uses, or not relevant — with the evidence for the match.

## 3. Prioritise

1. **Malicious package installed** — an incident, not an upgrade (section 5).
2. **Exploited in the wild** (CISA catalog) and the vulnerable code is reachable.
3. **High severity, reachable.** Check reachability: find calls to the affected
   function or uses of the affected feature (`git grep`); for Go, `govulncheck`
   checks the call graph. Unreachable is still worth fixing, just later.
4. Everything else, batched.

## 4. Fix

Use the lowest version that fixes every advisory against the package (the scan's
target, confirmed against the advisory's "patched versions"). Read the changelog
between the installed and target versions for breaking changes before upgrading.

| Ecosystem | Upgrade one package |
| --- | --- |
| uv | `uv lock --upgrade-package <name>`; a direct dependency's floor goes in `pyproject.toml`; a transitive one blocked by a parent's cap goes in `[tool.uv] constraint-dependencies` |
| poetry | `poetry update <name>`, or raise the constraint with `poetry add <name>@^<target>` |
| npm / yarn | `npm install <name>@<target>` if direct; `overrides` (npm) or `resolutions` (yarn) if transitive |
| pnpm | `pnpm update <name>`; transitive via pnpm overrides (check where your pnpm version reads them) |
| Go | `go get <module>@v<target> && go mod tidy` |
| Cargo | `cargo update -p <name> --precise <target>` |
| Docker | bump the base tag to the fixed patch (or pin a digest) |
| This machine | tell the user the command for their version manager; don't change it unasked |

Then: run the tests, run `scan` again and confirm the advisory is gone, and
check the lockfile diff touches only the intended packages. Follow
`dependency-safety` for everything else — a security fix is a reason to change a
dependency, not licence to change others.

**No fix released yet:** mitigate (disable the feature, change config, block the
input) and record the decision where the scanner reads it, with a reason and an
expiry, so it resurfaces:

```toml
# osv-scanner.toml, next to the lockfile
[[IgnoredVulns]]
id = "GHSA-xxxx-xxxx-xxxx"
ignoreUntil = 2026-12-01
reason = "No fix released; feature X disabled in config/app.toml"
```

## 5. Malicious or compromised package

Stop and tell the user before anything else. Upgrading is not enough:

- Find when the bad version entered (`git log -p -- <lockfile>`, `git log -S'<name>'`) and
  every machine and CI run that installed it since.
- Assume every secret that environment could read is exposed — `.env` files, package
  registry tokens, cloud and CI credentials, SSH and wallet keys — and list them for rotation.
- Pin to a known-good version, clear package caches (`npm cache clean --force`,
  `uv cache clean <name>`), reinstall from the cleaned lockfile.

## Report

Lead with what needs action now. One table per scope (repo, this machine,
services): package or product, installed → fixed version, exploited or not,
reachable or not, and the action taken or recommended. End with what was not
checked — unscanned ecosystems, unreachable feeds, items you could not identify.
