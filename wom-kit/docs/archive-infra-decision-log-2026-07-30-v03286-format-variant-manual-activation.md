# Archive Infrastructure Decision Log — v0.3.286 Manual `format_variant`

Date: 2026-07-30
Status: accepted for implementation

## Context

Beta feedback identified reviewed pairs such as lecture material and notes that
can sometimes carry substantially the same intellectual content in another
format. The existing `references`, `derived`, and `embed` relations cannot state
that narrower meaning. However, the observed labels alone are not reliable
enough to infer the relation: many similarly named pairs contain different
intellectual content.

WOM already exposed `format_variant` as a provisional review meaning, but it was
not a durable link type. Existing approval-gated `zettel-edge`, receipt, revert,
and `related-zets` paths can support the relation without a new writer.

DCMI defines `hasFormat` and `isFormatOf` as inverse directional properties for
substantially the same resource in another format:

- <https://www.dublincore.org/specifications/dublin-core/dcmi-terms/terms/hasFormat/>
- <https://www.dublincore.org/specifications/dublin-core/dcmi-terms/terms/isFormatOf/>

The current WOM evidence does not prove which member of a pair was the
pre-existing resource. Reusing either DCMI term as WOM's stored edge name would
therefore assert direction that the evidence does not support.

## Decision

Activate `format_variant` as a WOM-local application-profile link type.

- From: `Zettel`
- To: `Zettel | OriginalObject`
- Meaning: the target is an alternate rendition of the same intellectual
  content as the human-selected source anchor.
- The stored direction does not claim that the source is older, original, or
  canonical.
- The relation is conceptually close to the DCMI format pair, but it is not an
  exact mapping to either directional DCMI property.
- Only a human-reviewed `zettel-edge` dry-run/approve flow may write it.
- `zettel-edge-batch` must always route this type to `human_review_queue` with
  `manual_single_edge_review_required`, even when a policy lists it as
  auto-writable; the batch path must not write it.
- Store one reviewed assertion per pair. Do not generate a reciprocal edge.

The relationship vocabulary row becomes `active_mapping` with
`active_edge_type: format_variant`. The provisional candidate heuristics stop
offering `format_variant`; activation does not create an automatic classifier.

Archives with a local, stale `zettel-kasten/types.yml` adopt the base definition
through the existing append-only `base-link-types` migration. An archive's
pre-existing custom record with the same id remains untouched and must be
reviewed rather than overwritten.

## Approval Ladder

1. Preview base-type synchronization with
   `archive migrate <root> --target base-link-types --dry-run --format json`.
2. Approve it with `--approve --reviewed-by <actor>` only after reviewing any
   `present_not_overwritten` result.
3. Preview one relation with
   `archive zettel-edge <root> --from-zettel <anchor> --target <variant>
   --edge-type format_variant --dry-run --format json`.
4. Approve that exact human judgment with `--approve --reviewed-by <actor>`.
5. If the judgment was wrong, use the existing receipt-bound `revert-edge`
   preview/approve flow.

## Consequences

- New and inherited archive models can validate reviewed `format_variant`
  writes without a new schema, CLI, MCP writer, or provider integration.
- For a `Zettel -> Zettel` relation, `related-zets` can find the stored edge
  from either zettel endpoint while preserving the one stored assertion. This
  does not claim an object-endpoint query for `OriginalObject` targets.
- Type synchronization remains append-only and has no automatic revert. The
  semantic contract must therefore remain stable.
- Existing `references` edges and existing corpus records are unchanged.

## Non-goals

- No title-, filename-, or node-category-based pairing.
- No migration or reclassification of existing `references`.
- No reciprocal edge generation.
- No activation of `sequence`, `responds_to`, `fulfills`, or `enabling`.
- No DCMI or IFLA ontology expansion.
- No beta archive write.
- No Notion mirror/locator restoration in this release.
