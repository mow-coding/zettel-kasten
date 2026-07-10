# Seeded Reading Route Evidence

Status: implemented in v0.3.210

## Purpose

`seeded_connection_walk` already places tied nodes near a verified start zet
without dropping disconnected nodes. `projection=routed_reading` optionally
explains why each node appears in that order.

Use it only when the host or human needs the explanation. Normal
`projection=reading` stays smaller and remains the recommended exhaustive first
pass when route reasons are not needed.

## Command

```powershell
archive zet-catalog <archive-root> `
  --status canonical `
  --projection routed_reading `
  --coverage-mode strict `
  --order seeded_connection_walk `
  --start-zettel-id <verified-id> `
  --max-estimated-tokens 8000 `
  --dry-run `
  --format json
```

`routed_reading` without `seeded_connection_walk` blocks. A host must not invent
a seed from natural-language similarity.

## Per-Item Evidence

Each routed item keeps the normal abstract, facets, tie summary, and complete
safe edge projection. It also adds `catalog_order_index` and `reading_route`.

The route reason is one of:

| Reason | Meaning |
| --- | --- |
| `verified_seed` | This item is one of the verified starting entries. |
| `connection_passage` | The breadth-first walk reached this item through a safe frontmatter zet edge. |
| `fallback_component_root` | The seeded prefix ended and this item starts the next disconnected component or isolated node. |

A connection passage reports its distance, prior catalog order index and id,
edge type, and `walk_direction`. `with_stored_direction` means parent-to-child
matched the stored source-to-target direction;
`against_stored_direction` means the read walked the same stored edge in the
opposite direction. The stored edge itself is never rewritten.

## Duplicate IDs And Strict Chains

Catalog entries are files, so duplicate zet ids must not make one file vanish.
Strict continuation v0.3 hashes a snapshot-bound identity derived from the
file's path-order ordinal and status. It does not hash only the public zet id.

The raw entry-identity values and archive paths are not returned. The page
returns only `page_entry_identity_sha256`, and the continuation token binds the
identity basis. This is accidental-drift evidence, not a signature,
attestation, credential, or durable receipt.

## Cost Boundary

Route explanations consume tokens. On a temporary 10,000-node chain with
120-character abstracts and an 8,000-token item budget:

- compact `reading`: 179 pages, 1,414,699 estimated item tokens, 50.8 seconds;
- `routed_reading`: 257 pages, 2,026,799 estimated item tokens, 53.8 seconds.

These are local synthetic observations, not an SLA or provider-reported token
count. Both modes returned all 10,000 unique ids, stayed under the page budget,
and reached all three v0.3.209 readiness signals.

## Closed Actions

Routed reading reads frontmatter only. It performs no LLM call, body scan,
ranking, semantic similarity, edge rewrite, map generation, route persistence,
or WOM-owned goal/loop creation.
