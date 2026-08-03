# Private Objet Finder

Status: implemented in v0.3.298

`archive find-objet` performs a bounded, exact lookup against WOM's current
private generated alias index. It is a CLI-only, read-only command for the
explicit `private_archive` audience.

## Command

Use one query transport:

```text
archive find-objet <archive-root> \
  --audience private_archive \
  --query-profile literal_unicode \
  --query <value> \
  --limit 20 \
  --format json
```

For better local process privacy, pass the query through stdin:

```text
archive find-objet <archive-root> \
  --audience private_archive \
  --query-profile utf8_percent_encoded_component \
  --query-stdin \
  --format json
```

`--query` can be visible to the local operating system as a process argument.
The result reports that exposure as a Boolean warning but never reflects the
query value. `--query-stdin` avoids that argv exposure.

## Exact scope

The finder:

- reuses the pinned filename normalization and alias-key derivation;
- matches only exact SQLite `BINARY` alias equality;
- deduplicates globally by `object_id`;
- returns only an already stored and exact-validated private safe-label
  projection;
- uses one opaque `mode=ro`, `query_only=ON` transaction for health, lookup,
  projection validation, and the final snapshot check; and
- writes no archive, database, sidecar, journal, temporary file, receipt, or
  log.

It does not use FTS, `LIKE`, substring, prefix, suffix, regex, fuzzy matching,
ranking, or a winner heuristic. It opens no object bytes and calls no network,
provider, credential, external-store, or MCP surface.

## Result meanings

The five closed statuses are:

- `blocked`: the request or trusted local evidence is unsafe or invalid;
- `search_incomplete`: the private generated index cannot support a
  conclusive lookup;
- `not_found_in_index`: no exact match exists in the complete current private
  index;
- `found`: exactly one distinct objet matched; and
- `ambiguous`: more than one distinct objet matched, with no winner chosen.

`not_found_in_index` is deliberately narrow. It is not archive-wide absence,
object-storage integrity, source-reference coverage, external-store coverage,
or remote-backup proof.

Exit code `0` covers the three complete lookup outcomes, exit code `1` means
`search_incomplete`, and exit code `2` means `blocked`.

## Privacy and output

JSON and text contain closed codes and authorized stored projections only.
They contain no raw, decoded, normalized, stemmed, folded, or derived query;
archive path; SQL; exception text; source identifier; provider locator;
credential; or secret value. Parser failures also go through the private-safe
finder grammar rather than standard `argparse` diagnostics.

If semantic result validation or rendering fails, the command emits one fixed,
ASCII-only fallback. Terminal delivery is best effort and does not change the
already computed semantic exit code.
