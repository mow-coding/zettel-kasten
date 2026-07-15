# Decision Log: Philosophy Implementation Traceability

Date: 2026-07-16
Status: accepted for v0.3.252

## Decision

Publish paired English/Korean evidence maps that connect WOM's core philosophy
to implemented runtime surfaces, regression evidence, and explicit remaining
boundaries. Correct the stale current-status wording in the original node-first
decision without erasing what that document truthfully did not claim in
v0.3.203.

## Context

WOM's artifact-first, human-drift, Memento Problem, node-first reading, local
sovereignty, and approval doctrines were implemented across many small
releases. The public evidence was distributed across philosophy documents,
release notes, runtime instructions, the capability matrix, commands, and
tests. One early decision still said the node-first direction was not
implemented even though later releases had implemented it.

That distribution created two audit risks:

1. a reviewer could mistake implemented behavior for philosophy-only intent;
2. a reviewer could mistake structural or receipt evidence for semantic truth,
   live remote proof, or product completeness.

## Consequences

- One bounded traceability map now separates engineering implementation,
  real-use validation, and provider-specific future work.
- Every core row includes a mechanism, regression evidence, and honest
  boundary rather than a bare completion label.
- The node-first decision keeps its historical v0.3.203 non-claim and gains a
  dated implementation follow-through.
- The Agent Skill remains progressively disclosed. The project does not add a
  new philosophy command or force an operating AI to preload another document
  during ordinary archive work.
- This checkpoint adds documentation and regression coverage only. It grants
  no new write, model, network, provider, database, graph, or identity-merging
  authority.
