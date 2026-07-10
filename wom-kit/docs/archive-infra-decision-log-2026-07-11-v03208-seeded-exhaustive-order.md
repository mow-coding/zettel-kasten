# Archive Infra Decision Log - v0.3.208 Seeded Exhaustive Order

Date: 2026-07-11
Release: v0.3.208

## Context

WOM could now enumerate every abstract and tie with strict completion, but only
in archive-relative path order. The project philosophy says every node remains
visible while local ties should help the host decide what to encounter first.

## Decision

- Let a host supply already verified zet ids as optional reading-order seeds.
- Use incoming/outgoing edges as undirected passages for order only.
- Walk seed components breadth-first, then every remaining component in path
  order.
- Block absent, unsafe, or missing seeds instead of guessing.
- Preserve duplicate-id file nodes and report all-node evidence.
- Bind strict continuation to the order and seed-list fingerprint.
- Do not rank, read bodies, call models/providers, write maps, or persist loop
  state.

## Consequences

- A goal-relevant known node can be encountered first without turning WOM into
  top-k retrieval.
- Disconnected and isolated memory still participates in the same complete
  pass.
- Edge direction remains canonical metadata; bidirectionality exists only in
  this derived reading order.
- In-flight v0.3.207 strict tokens restart after upgrade because continuation
  schema v0.2 adds seed-order binding.
