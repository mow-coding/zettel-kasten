# Archive Infra Decision Log - Node-First Exhaustive Traversal

Date: 2026-07-11
Status: accepted design direction; not yet implemented

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
- The existing one-zet overview and AI start-here commands are useful building
  blocks, but an archive-wide abstract enumeration and ordering surface remains
  future work.

## Non-Claim

This decision records product and architecture direction only. It does not claim
that archive-wide abstract enumeration or host-driven exhaustive traversal is
implemented in v0.3.203. Persisted traversal checkpoints are not accepted as a
WOM responsibility by this decision and remain a separate future question.

## Open Terminology Question

The current public naming baseline defines `node` as a subject/archive
participant, while the current local graph index stores edges between zet ids
and therefore treats zets as graph vertices in implementation. The present
node-first reading direction does not silently resolve that collision.

Before a schema or command is named around `node`, the project must review
whether to distinguish `archive node` from `zet node`, or adopt another explicit
model. No existing identifier or public term is renamed by this decision.
