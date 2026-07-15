# Decision Log: Runtime Skill Host Lifecycle

Date: 2026-07-15
Status: Accepted for v0.3.244

## Context

v0.3.242 made WOM-kit a cleanly installable Python tool and v0.3.243 made its
runtime skill small and progressively readable. The remaining low-friction
activation gap was host discovery: a person or AI still had to know where to
copy the skill. A blind post-install copy would be convenient but would blur
Python package authority, AI-host configuration ownership, and human approval.

## Decision

1. Add CLI-only `runtime-skill-status`, `runtime-skill-install`, and
   `runtime-skill-uninstall` commands.
2. Default Codex user scope to the current official `$HOME/.agents/skills`
   location; support repository `.agents/skills` only with an explicit existing
   `--repo-root`.
3. Require explicit `custom/custom --skills-root` options for other hosts; do
   not guess Claude or another product's directory.
4. Keep status and install/uninstall dry-runs path-redacted and write-free.
5. Bind every approval to the exact target-path hash, source-package hash,
   target state, prior manifest hash, and package version.
6. Require a safe reviewer id plus the dry-run plan SHA-256 before writing.
7. Write a self-checking local ownership manifest with relative paths, bytes,
   and SHA-256, but no absolute path, archive data, account, or secret.
8. Update or remove only when every managed file still matches that manifest.
   Never adopt, overwrite, or delete an unmanaged or human-edited directory.
9. Use an exclusive lock, outside-active-root private staging directory,
   backup or uninstall tombstone, and post-write verification.
10. Add no MCP write tool, archive write, provider call, network call, generated
    graph, or automatic wheel post-install hook.

## Consequences

An AI operator can now take a beginner from installed WOM-kit to an active
Codex skill through one preview-and-approval conversation without asking the
person to find configuration folders. Convenience remains subordinate to
explicit ownership and stale-plan protection. Plugin-based workspace
distribution and PyPI publication remain later, separate decisions.
