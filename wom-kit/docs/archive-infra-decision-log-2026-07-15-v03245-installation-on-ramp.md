# Decision Log: Top-Level Installation On-Ramp

Date: 2026-07-15
Status: Accepted for v0.3.245

## Context

The dedicated WOM-kit README and installation guides were actionable, but the
root public READMEs mentioned installation only inside long capability lists.
A first-time visitor could understand the product without finding the command
needed to try it.

## Decision

1. Put one bounded Quick Start before the capability inventory in both root
   READMEs.
2. Show the exact tagged wheel, isolated `uv` install, and version check.
3. State the non-PyPI boundary instead of implying bare `pip install` support.
4. Keep Python installation separate from the read-only Agent Skill activation
   preview and approval-gated host write.
5. Link to detailed guides instead of duplicating their lifecycle contract.
6. Update only the exact wheel version in this stable section on later releases.

## Consequences

The public showcase now has an executable first-use path without becoming a
landing page or duplicating the full manual. The change adds no installer side
effect, archive authority, host write, provider integration, or UI.
