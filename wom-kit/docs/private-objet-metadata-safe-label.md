# Private Objet Metadata And Safe Labels

Status: pure contract implemented in v0.3.295

## Why This Contract Exists

Content-addressed storage correctly uses SHA-256 as object identity, but people
usually remember a document by a human name. A safe rediscovery path therefore
needs to preserve both facts without confusing them:

```text
SHA-256 remains identity.
Human names are provenance-bound aliases.
Aliases never rename bytes, merge objets, or prove object equality.
```

v0.3.295 defines the metadata and projection contract needed by later private
writers and finders. It does not register archive data, build an index, search
private names, open object bytes, or expose a new CLI or MCP tool.

## Public Schemas

The release publishes Draft 2020-12 schemas for:

- `wom-kit/private-objet-source-metadata/v0.1`; and
- `wom-kit/objet-safe-label-projection/v0.1`.

Both schemas use closed objects, required fields, strict enums, bounded
strings and arrays, exact lowercase SHA-256 identifiers, and audience-specific
branches.

A private metadata record binds one bounded source-name observation to one
SHA-256 objet. Multiple records may describe the same objet, but every record
keeps its own source snapshot and observation evidence digests.

## Identity And Evidence Boundaries

The record keeps these axes separate:

- original, decoded, NFC, NFD, stem, and extension name evidence;
- source-declared MIME evidence;
- source-observed size evidence;
- source-system and source-record/attachment provenance;
- candidate label evidence and review evidence; and
- private or restricted protection level.

v0.1 deliberately does not infer MIME from a suffix or the operating system.
It accepts only `unknown` or `source_declared` MIME basis, only `unknown` or
`source_observed` size basis, and keeps registry status, extension agreement,
and confusable checking at fixed `not_checked`/`unknown` states until a future
version has a separately reviewed evidence source and writer.

## Filename Normalization

The pure reference module supports either literal Unicode or one strict
UTF-8 percent-encoded component.

- Literal input is never percent-decoded.
- Encoded input is decoded exactly once.
- `+` remains a literal plus.
- Malformed escapes, invalid UTF-8, a UTF-8 BOM, residual `%HH`, path
  separators, NUL, controls, Unicode separators, and pinned bidi controls
  block derivation.
- NFC and NFD use `unicodedata2==17.0.1`, whose data version must be exactly
  Unicode 17.0.0.
- NFKC and NFKD never define the canonical filename.
- A filename or derived name longer than 512 Unicode scalars is blocked
  without truncation.

Stem and extension parsing is a platform-independent string algorithm. Only
ASCII full stop is a separator, and a suffix becomes an extension only when
every suffix scalar is ASCII.

## Pinned Search Keys

Case folding uses the complete non-Turkic Unicode 17 `C` and `F` mappings from
the official `CaseFolding.txt`. Whitespace and bidi classifications come from
the pinned Unicode 17 `PropList.txt`.

The canonical-caseless transform is:

```text
Q(X) = NFC_17(full_casefold_CF_17(NFD_17(X)))
```

WOM then applies a separate separator fold for the fixed Unicode White_Space
set plus ASCII underscore and hyphen. These values are search aliases only:
equal keys may produce more candidates, but never merge objects.

An exhaustive Unicode 17 scalar proof bounds every filename/stem key at
`4 * 512 = 2048` scalars. The implementation fails closed rather than
truncating if that invariant is ever violated.

## Projection And Privacy

Private and restricted projections select an eligible label by fixed kind
precedence and deterministic evidence ordering. Tied highest-priority
distinct values remain ambiguous; input order never selects a winner.

The `public_generic` branch is a different closed object. It can contain only
one closed generic family such as `document`, `image`, or `unknown`. It has no
free-form selected label, filename, source identifier, path, provider locator,
secret value, or private ambiguity detail.

Projection also requires explicit permission to disclose the SHA-256 object
identifier on the target surface. Missing permission produces a content-free
no-output refusal rather than a misleading blocked projection.

## Pure Runtime Boundary

`wom_kit.private_objet_metadata` operates only on in-memory strings, dicts,
and bounded lists. It:

- writes no files;
- reads no archive, SQLite database, credential store, or object bytes;
- calls no provider or network;
- exposes no CLI or MCP tool; and
- returns only closed wrappers and fixed content-free issue codes.

The runtime validator is dependency-light and does not import `jsonschema`.
CI separately uses `jsonschema[format-nongpl]==4.26.0` as a test-only Draft
2020-12 oracle and checks the required acceptance direction.

## Rediscovery Status

The checked-layer rediscovery plan now reports that the schema and pure
normalization contract exist, while keeping the private metadata layer
`not_implemented`. No approved writer, receipt-bound index, or private query
exists in v0.3.295, so the layer is still not complete and cannot support a
global absence claim.

## Deferred Work

- v0.3.296: approval-gated private metadata writer, immutable receipt, and
  replay/recovery;
- v0.3.297: receipt-bound generated-index ingestion and freshness;
- v0.3.298: local private finder; and
- v0.3.299: source-reference coverage versus storage integrity.

External local-store registration and byte verification remain later,
separately reviewed work.
