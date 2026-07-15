# Decision Log: Artifact Primacy And Human Drift

Date: 2026-07-15
Status: Accepted for v0.3.246

## Context

WOM has useful similarities to enterprise ontology systems: it needs typed
records, provenance, controlled writes, receipts, and maps that help an
operator navigate large data. But its primary subject is not a stable corporate
master-data domain. It is a human whose language, beliefs, priorities, and
interpretations can change over time.

Treating repeated labels as one resolved entity would make the archive look
clean while risking a false account of the person. The same label can carry a
different meaning in a different artifact or moment.

## Decision

1. Durable, time-situated artifacts and their chronology are WOM's primary
   evidence layer.
2. Entity matching, graph projection, embeddings, and indexes are regenerable
   reading aids. They are not canonical truth.
3. Matching labels never authorize a silent identity merge.
4. Contradiction, ambiguity, repetition, correction, and revision may remain as
   meaningful history.
5. `canonical` means the subject-approved current archive state. It does not
   certify objective or timeless truth.
6. Nodes, ties, and edges are reviewable relationship claims and reading
   routes. They do not prove identity by themselves.
7. AI may re-infer context at reading time using available tokens and model
   capability. Inference is replaceable; local artifacts, provenance, and
   receipts remain durable.

## Consequences

- Future entity assistance must produce candidates with provenance, scope, and
  review state, never an automatic global merge.
- Search databases and graph stores remain rebuildable map backups or
  acceleration layers under local archive authority.
- Revision and correction flows preserve prior evidence instead of laundering
  it into one timeless representation.
- First-read abstracts may route an AI efficiently, but do not replace complete
  artifact reading when the task needs it.
- Product success includes helping a person see how their own meanings and
  judgments changed, not merely producing a visually coherent graph.

## Non-Goals

This decision adds no entity resolver, model call, graph mutation, schema
migration, archive write, UI, or automatic interpretation. It establishes the
design boundary that such future work must respect.
