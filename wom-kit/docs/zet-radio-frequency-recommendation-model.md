# ZET Radio-Frequency Recommendation Model

Date: 2026-05-27
Status: public model baseline

## Summary

v0.2.48 records a future recommendation model for ZET closed sharing.

The model is deliberately conservative:

```text
followed / neighbor feed -> explicit relationships and permissions
recommended / broadcast feed -> user/node-owned selector logic
```

Many Web2 social systems blend followed content with recommended content in one feed. That can be useful, but when the ranking logic is opaque and platform-owned, users may not know why they are seeing something, whether it is relationship-based, whether it is advertising-shaped, or whether the feed is optimizing for engagement over trust.

ZET should not copy that default. ZET should start from explicit relationships, delegates, groups, permission graphs, and user-owned archive context. Recommended or broadcast content can exist later, but it should be selected by inspectable, configurable, explainable logic owned by the user or node.

## Radio-Frequency Metaphor

The radio-frequency metaphor is product language.

It means:

- a node may choose a visible ZET channel, topic, scope, or broadcast lane,
- the node may tune into that channel for a specific purpose or time window,
- the node should be able to inspect the selector that chose the recommended items,
- the node can switch, pause, narrow, or replace the selector.

It does not mean WOM-kit implements radio hardware, live streaming, wireless transport, P2P relay, provider sync, or real ZET transport in v0.2.48.

## Prompt-As-Algorithm

Future selectors may be expressed as:

- a prompt-like policy,
- a rule bundle,
- a configuration object,
- code,
- a signed policy artifact,
- a future capability-bound recommendation profile.

In this document, prompt-as-algorithm does not mean only an LLM prompt. It means a human-readable and inspectable selection policy that a node can review before allowing it to shape a recommended feed.

v0.2.48 does not execute selectors, rank zets, fetch remote content, update feeds, train models, or run recommendation inference.

## Feed Classes

### Followed / Neighbor Feed

A followed or neighbor feed should be based on explicit relationships:

- delegated access,
- known neighbor nodes,
- groups,
- workspace membership,
- permission scopes,
- receiver-side attestation or review state.

This feed class should not silently insert unrelated recommendations as if they came from followed relationships.

### Recommended / Broadcast Feed

A recommended or broadcast feed may later include content outside the immediate relationship graph.

Its minimum future provenance should explain:

- which selector was used,
- which frequency/channel/source was tuned,
- which time or observation window was considered,
- which feed class produced the item,
- which scope or permission made the item visible,
- whether the item was reviewed or attested,
- whether mirroring or projection was allowed.

This is recommendation as a user-owned instrument, not an invisible central command.

## Future Recommendation Provenance

A future recommendation record should be able to preserve fields such as:

```text
selector_ref
selector_owner
selector_form
feed_class
frequency_ref
source_scope
permission_scope
observation_window
selection_explanation
review_state
attestation_state
projection_allowed
mirroring_allowed
central_black_box_ranking_used
```

The default should be:

```text
central_black_box_ranking_used: false
```

If a future implementation uses an external ranking service, that fact should be visible in provenance and should not be disguised as neighbor/followed content.

## Relationship To ZET Closed Sharing

The v0.2.47 closed sharing model defines ZET as the future sharing/SNS layer above the base zettel-kasten infrastructure.

v0.2.48 adds a recommendation philosophy for that future layer:

```text
closed sharing first
explicit relationships first
inspectable recommendation second
central opaque ranking never as the hidden default
```

This keeps WOM centered on subject-owned memory and explainable circulation rather than platform-owned attention routing.

## Non-Goals

v0.2.48 does not:

- add a CLI recommendation command,
- add an MCP recommendation tool,
- fetch recommended zets,
- rank or rerank feeds,
- update neighbor feeds,
- call providers,
- publish to WordPress,
- write projection records or receipts,
- run real ZET transport,
- train models,
- run backpropagation,
- add Redis, queues, workers, or a feed service,
- create trust, import, acceptance, attestation, signatures, minting, anchoring, delegation, sharing, payments, staking, consensus, blockchain, or full-auto behavior.
