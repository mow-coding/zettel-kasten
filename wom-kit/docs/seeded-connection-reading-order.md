# Seeded Connection Reading Order

Status: implemented in v0.3.208

## Purpose

Every selected zet must still be read, but the first nodes can be more useful
when the host goal already identifies a verified zet. This feature changes only
the exhaustive catalog order. It is not retrieval, relevance ranking, or a
global archive map.

## Use

```powershell
archive zet-catalog <archive-root> `
  --status canonical `
  --projection reading `
  --coverage-mode strict `
  --order seeded_connection_walk `
  --start-zettel-id <verified-zet-id> `
  --cursor 0 `
  --dry-run `
  --format json
```

Repeat `--start-zettel-id` for up to 32 verified ids. MCP uses `order` and
`start_zettel_ids`.

Use seeds only when the human, host goal, saved view, or prior verified tool
output already identifies the ids. Do not invent an id from natural-language
similarity. If there is no verified seed, use normal path order.

## Ordering Algorithm

1. Read all selected local frontmatter, as the catalog already does.
2. Resolve every supplied seed inside that selected scope; a missing seed
   blocks.
3. Treat safe incoming and outgoing zet edges as undirected reading passages.
4. Breadth-first walk the seed components, preserving seed input order and
   archive-relative path order for equal-distance neighbors.
5. For every still-unvisited path in archive-relative order, breadth-first walk
   that disconnected component.

The algorithm keys file nodes by their catalog entry, not only by zet id, so a
malformed archive with duplicate ids does not silently lose files.

## Evidence

`order_evidence` reports:

- requested/resolved/missing seed ids;
- seed entry and seed-connected prefix counts;
- fallback component and connection-passage counts;
- all-node preservation;
- that edges were used bidirectionally only for reading order;
- that edge meaning/direction was not rewritten;
- that no ranking or global map was produced or persisted.

Strict continuation token v0.2 binds the order descriptor and a fixed-size
SHA-256 fingerprint of the ordered seed list. Changing seeds mid-pass blocks.
Raw seed ids are not embedded in the token.

## Boundaries

The walk:

- does not read zet bodies;
- does not search embeddings or call an LLM/provider;
- does not score relevance;
- does not hide disconnected or isolated nodes;
- does not edit edges;
- does not create a generated index/map;
- does not persist host goal, loop, cursor, or traversal state.
