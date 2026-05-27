# WOM Naming And Terminology

Status: public naming baseline
Date: 2026-05-23

This document defines the current product-language direction for WOM.

It is a naming freeze for public-facing language, not a guarantee that every internal file path, schema field, and compatibility command has already been renamed.

For the current Korean product-language explanation baseline, see [Korean Product Language Baseline](korean-product-language-baseline.ko.md).

## Umbrella Name

```text
WOM
Widesider of Modernity
```

WOM is the umbrella name.

The name means: if modernity is a spectrum, WOM stands near its frontier and tries to widen the horizon that humans can perceive.

WOM is broader than a note app, a SaaS archive, or a blockchain token project. It is the worldview around a local-first, AI-native, Web3-oriented archive and communication system.

## Root, Primitive, Communication Layer, Node

Canonical public language:

```text
WOM              -> overall umbrella / worldview
zettel-kasten    -> historical root and local archive method
zet              -> unit document minted from a zettel-kasten
ZET              -> zettel-kasten-based communication method / service / protocol layer
node             -> subject/archive participant
tie              -> candidate relationship/capability term between nodes
```

`zettel-kasten` remains important because the project began from the note-box tradition associated with Niklas Luhmann.

But the active product unit is `zet`, not `zettel`.

`ZET` is different from `zet`.

`zet` names the unit minted inside a zettel-kasten.

`ZET` names the communication layer built from zets: it can behave like a messenger in 1:1 topology, a feed/SNS in 1:many topology, or a collaboration workspace in many:many topology.

Use:

```text
zet
minted zet
draft zet
foreign zet
ZET protocol
ZET communication layer
ZET-based SaaS
```

Avoid as current product language:

```text
the capitalized singular form of zet
mixed-case spellings of WOM
lowercase spellings of WOM
zettel as the active unit
canonical zettel in public copy
mint-zettel as the preferred command name
```

Implementation compatibility note: current v0.2 file paths and code still contain `zettel`, `zettels/`, `mint-zettel`, and related schema names. As of `v0.2.13`, `mint-zet` exists as the preferred CLI alias, but the older names remain compatibility surfaces. As of `v0.2.14`, public-facing documents distinguish `WOM`, `zet`, and `ZET`.

## Lifecycle

Canonical WOM lifecycle:

```text
mint -> delegate -> attest -> anchor
```

Meanings:

- `mint`: issue a `zet` into a node's private archive memory.
- `delegate`: give a scoped capability around a minted `zet`.
- `attest`: verify a foreign `zet`, its issuer, integrity, and delegated conditions.
- `anchor`: place an attested foreign `zet` into a node's local meaning network.

Legacy or compatibility language:

- `promote` -> legacy compatibility for old minting behavior.
- `share` -> legacy/general explanation; product language should say `delegate`.
- `download` / `receive` -> avoid as core language; product language should say `attest`.
- `save` -> avoid as core language; product language should say `anchor` when local meaning placement is intended.

## Parcel And Admit

Current implementation language has:

```text
pack
workpack
import
```

Preferred product direction:

```text
workpack -> parcel
pack     -> parcel / create parcel
import   -> admit, when bringing a parcel or foreign zet into a node after checks
```

For raw source/provider material, use:

```text
ingest source
register source
scan source
```

This distinction matters:

- `admit` belongs to governed cross-boundary material.
- `ingest/register/scan` belong to local source onboarding and metadata mapping.
- `parcel` is a bounded portable unit, closer to a shareable plot/package than a generic file bundle.

## Proof, Credential, Attestation

Current implementation language uses `receipt`.

`receipt` is acceptable as a v0.2 implementation term because blockchains also use transaction receipts, and because the current code already has schema-backed receipt files.

However, product language should move toward stronger distributed-trust words:

```text
mint receipt          -> mint proof
delegate receipt      -> delegation credential or delegation proof
attestation receipt   -> attestation
anchor metadata       -> anchor proof / anchor mark
```

Recommended near-term rule:

- keep `receipt` in file paths and schemas for v0.2 compatibility,
- introduce `proof` and `credential` in public docs,
- decide field/path migrations only after aliases exist.

## Credit

`credit` is not recommended as the core evidence-object replacement.

It has useful associations:

- attribution,
- recognition,
- trust,
- accounting,
- future settlement,
- value or contribution.

But it also risks implying:

- money,
- score,
- debt,
- platform reputation.

Recommended use:

```text
credit -> future attribution / contribution / settlement layer
proof or credential -> core evidence layer
```

## Current Compatibility Position

As of `v0.2.14`:

- `delegate-zet` is already aligned with product language.
- `attest-zet` and `anchor-zet` are aligned with product language.
- `mint-zet` is the preferred CLI surface for minting; `mint-zettel` remains a compatibility alias.
- `zet` is always lowercase when referring to the minted unit.
- `ZET` is uppercase when referring to the communication method/service/protocol layer.
- `WOM` is always uppercase.
- `promote` and `share` should remain legacy compatibility commands only.
- `parcel` is the preferred CLI surface for creating a portable bounded unit; `pack` remains a compatibility alias.
- `admit --dry-run` is the preferred CLI surface for previewing governed parcel/workpack admission; `import --dry-run` remains a compatibility alias.
- `workpack` remains the v0.2 storage path/folder compatibility term until a safe migration exists.
- `receipt` should remain implementation-compatible while product copy begins introducing `proof` and `credential`.
- Markdown remains an authoring/import compatibility format while WOM Safe HTML Profile becomes the long-term canonical/interchange/rendering direction.

Short form:

```text
WOM
node
zet
ZET
mint -> delegate -> attest -> anchor
parcel -> admit
proof / credential / attestation
WOM Safe HTML Profile
```
