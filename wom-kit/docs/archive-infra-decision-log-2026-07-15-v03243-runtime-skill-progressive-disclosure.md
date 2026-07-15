# Decision Log: Runtime Skill Progressive Disclosure

Date: 2026-07-15
Status: Accepted for v0.3.243

## Context

The shipped WOM runtime skill had grown to 731 lines and 5,880 words. It held
valuable safety history, but an AI host either had to spend context on the
whole document or risk skipping it. Graphify-style low-friction activation and
the Agent Skills package convention show a useful interaction principle: keep
the first contact small and route deeper reading by task.

## Decision

1. Convert `wom-archive` to a `SKILL.md` package with standard `name` and
   `description` frontmatter.
2. Keep the root under 200 lines and 1,400 words.
3. Route ordinary work into five focused references.
4. Preserve the complete previous contract as a searchable advanced reference.
5. Require every reference to be directly discoverable from the root.
6. Add a read-only checker for metadata, budgets, links, confinement, symlinks,
   and critical safety phrases, and make it a release-readiness child gate.
7. Include the entire package in the deterministic installed-wheel resource
   manifest and clean-install verification.
8. Do not install into any AI host directory in this release.
9. Do not make the skill, a generated graph, or an index canonical WOM memory.

## Consequences

Common archive sessions begin with much less instruction text. Exact advanced
rules remain available and test coverage now evaluates the whole skill package.
A future host installer can build on this package, but it must have a separate
dry-run, explicit approval, collision, receipt/manifest, update, and uninstall
boundary.
