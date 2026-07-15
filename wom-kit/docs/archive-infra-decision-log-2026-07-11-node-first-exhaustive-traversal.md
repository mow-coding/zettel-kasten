# Archive Infra Decision Log - Node-First Exhaustive Traversal

Date: 2026-07-11
Updated: 2026-07-16
Status: accepted at v0.3.203; core traversal implemented in v0.3.204-v0.3.216; private pass artifact lifecycle implemented in v0.3.217

## Context

WOM already supports overview-first reading for one zet and a compact AI
start-here surface. A clarification was needed about the role of generated maps
and retrieval when an archive contains hundreds or thousands of nodes.

## Decision

WOM is node-first. Within a declared task scope, the AI must account for every
node required by the goal. Retrieval ranking controls reading order; it must not
silently shrink exhaustive work into a top-k subset.

Goal and loop belong to the host LLM application's interaction model, not to
WOM's archive model. WOM supplies the local memory and reading surfaces; Claude,
Codex Desktop, or another host owns task branching, continuation, and completion
UX.

The intended integration boundary is:

1. The host application defines the goal, corpus boundary, and completion
   condition.
2. WOM makes the compact abstract data for every node in scope deterministically
   enumerable.
3. The host orders subsequent reading from node content and node-local ties and
   edges.
4. WOM keeps stable node identity and change evidence available so a host can
   distinguish the declared scope from later archive changes.
5. The host application continues or stops through its own goal/loop UX.

A global map may be used as a derived accelerator, but it is not canonical
memory and must not control archive meaning. It must remain replaceable and
recoverable from the local nodes and their relationships.

## Consequences

- `node` is the primary unit of AI traversal.
- `tie` and `edge` are local passages, not subordinate decorations on one
  authoritative global map.
- WOM must remain compatible with host applications that provide goal/loop UX,
  without pretending that goal or loop is a WOM archive primitive.
- Read order is an optimization surface even when coverage is exhaustive,
  because it changes repeated reads, context reconstruction, and reasoning
  overhead.
- A changing corpus requires stable identity and change evidence so host
  applications can establish their own snapshot or change boundary.
- The one-zet overview and AI start-here commands remain entry surfaces. The
  archive-wide implementation now continues through `first-read-readiness`,
  strict paged `zet-catalog`, MCP continuation, token and response-envelope
  budgets, seeded reading order, routed reading evidence, and the one-process
  `zet-catalog-pass`.

## Historical v0.3.203 Non-Claim

At the time this decision was accepted, it recorded product and architecture
direction only. It did not claim that archive-wide abstract enumeration or
host-driven exhaustive traversal was implemented in v0.3.203. That historical
non-claim remains true for v0.3.203 and must not be rewritten as if the feature
already existed in that release.

## Implementation Follow-Through

The direction was implemented incrementally after v0.3.203:

- [zet Abstract And Live Catalog](zet-abstract-catalog.md) records the
  v0.3.204-v0.3.216 path from deterministic enumeration through strict compact
  continuation and one-process completion.
- [zet Catalog Scale And Token Budget](zet-catalog-scale-and-token-budget.md)
  records bounded host-context behavior.
- [zet Catalog Pass Artifact Lifecycle](zet-catalog-pass-artifact-lifecycle.md)
  records the v0.3.217 SHA-bound private read and cleanup boundary.
- [WOM Philosophy Implementation Evidence](philosophy-implementation-evidence.md)
  maps this mechanism to the larger Memento Problem and artifact-primacy
  doctrine without treating structural coverage as semantic quality.

WOM still does not persist a canonical global traversal map, goal, or loop.
Strict catalog sessions and the private pass artifact are bounded reading
mechanisms. The host owns its task goal and continuation UX.

## 2026-07-16 Terminology Resolution

The original decision text above is preserved because `node-first` was the
wording accepted at v0.3.203. The current public naming baseline reserves
`node` for a subject/archive participant. The local graph implementation may
treat zet ids as `zet vertices`, but current public and runtime guidance calls
them `zets`, `zet entries`, or an exhaustive zet reading scope. It does not call
each document another node.

No schema, command, output key, historical release note, or decision-log title
is renamed here. Existing identifiers that contain `node` remain compatibility
surfaces. Any future identifier migration needs its own reviewed plan and must
not silently change archive meaning.
