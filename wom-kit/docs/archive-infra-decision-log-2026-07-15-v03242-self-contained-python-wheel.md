# Decision: Ship A Self-Contained Python Tool Wheel

Date: 2026-07-15
Status: Accepted for v0.3.242

## Context

WOM-kit already declared a Python package and four command entrypoints, but its
built wheel contained only Python modules. An installed wheel could print its
version and preview some commands, yet approved onboarding failed because the
schemas, templates, base rules, and release identity remained outside the
package. That was an install-shaped demo, not a usable tool distribution.

Graphify was reviewed as an external benchmark for low-friction command
installation, host activation, and progressively disclosed AI instructions.
Python tool installers such as `uv tool install` also provide a standard
isolated environment. Their distribution ergonomics are useful; a generated
graph is not adopted as WOM authority.

## Decision

1. Keep top-level schemas, templates, zettel-kasten rules, and release notes as
   the editable source of truth.
2. Synchronize the runtime subset into `wom_kit._resources` with a deterministic
   manifest containing exact byte lengths and SHA-256 values.
3. Prefer source-checkout resources during repository development and fall back
   to the package mirror in an installed wheel.
4. Refuse release when the committed package mirror drifts from source.
5. Build and install the wheel in a new virtual environment, require all four
   entrypoints, run onboarding preview and approved disposable creation, and
   finish with strict Doctor.
6. Attach only that verified wheel to the exact GitHub release.
7. Recommend isolated Python tool installation, with a dedicated `pip` virtual
   environment as the compatibility path.
8. Do not publish or claim the PyPI project name in this release. That first
   public registry action requires a separate deliberate decision and trusted
   publishing setup.
9. Do not make any generated graph, search index, or host skill canonical.
   Local reviewed zet, objet, relation, and receipt records remain authoritative.

## Consequences

A tagged WOM-kit wheel can now operate without a repository checkout. Package
installation remains separate from archive creation and writes no user data by
itself. The package mirror adds repository bytes, but duplication is controlled
by one source-to-manifest synchronization tool and exact tests. PyPI publication,
host skill installation, and a beginner-facing installer lifecycle remain later
steps rather than implied capabilities.
