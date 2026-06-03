# v0.2.x Freeze And v0.3.0 Entry Boundary

Date: 2026-06-02
Status: public checkpoint baseline

Update: v0.3.0 implements the first boundary described here as a CLI-only shared update attestation/review record and receipt write. The rest of the closed scope remains closed.

## Summary

v0.2.60 freezes the v0.2.x line as a conservative local-first foundation checkpoint.

In beginner terms:

```text
v0.2.x built the safe local ground.
v0.3.0 should start with one narrow approved write, not a whole transport system.
```

This document is a boundary document. It is not a feature promise and it does not add product behavior.

## What v0.2.x Established

The v0.2.x line opened safe local surfaces:

- local archive doctor checks,
- draft and mint lifecycle,
- receipt-backed local writes where already approved,
- read-only previews,
- dry-run planners,
- review indexes,
- public hygiene gates,
- capability matrix documentation,
- shared update review records,
- ZET transport threat modeling.

These surfaces are useful because they let WOM-kit inspect, plan, and explain before changing a private archive.

## What v0.2.x Did Not Open

v0.2.x intentionally did not open:

- real ZET transport,
- real key-sharing registry,
- real radio-frequency access creation,
- real mirroring payload or delivery,
- automatic neighbor feed updates,
- recommendation execution,
- trust/import/acceptance/anchor mutation,
- attestation/signature writes for shared updates,
- provider sync,
- WordPress publishing,
- projection writes or projection receipts,
- queues, workers, or background jobs,
- DID registry,
- wallet or private key custody,
- blockchain, token, system token, validator, governance, payment, staking, or consensus,
- model training, backpropagation, or full-auto execution.

That restraint is part of the architecture, not a missing shortcut.

## Proposed v0.3.0 Entry Boundary

The proposed first v0.3.0 boundary is one narrow receiver-side, approval-gated write.

The likely first write is:

```text
attestation/review record + receipt
for an already-reviewed shared or foreign update
```

That first write must remain:

- replay-gated,
- human-approved,
- local-first,
- body-safe,
- scope-limited,
- receipt-backed.

It must not imply:

- real ZET transport,
- automatic feed update,
- anchor or apply behavior,
- trust graph mutation,
- provider sync,
- WordPress publishing,
- full-auto behavior,
- blockchain, token, system-token, or governance behavior.

## Header / Body Safety

The `header` remains the safe guide and index surface.

The `body` remains private unless a human explicitly chooses a later approved path. A review record can carry metadata, hashes, refs, provenance, and receipt references without exposing private body content.

For WOM-kit, body-safe means:

- no raw private `body` text,
- no local absolute paths,
- no provider private URLs,
- no raw tokens or secrets,
- no private source/original objet filenames,
- no AI conversation body text unless explicitly approved in a later local archive workflow.

## Public Proof Boundary

ZET should not jump straight to a full blockchain.

The conservative lesson from InfraBlockchain / COOV-style public proof systems is:

```text
private personal data stays local/off-chain/on-device,
public infrastructure holds only minimal verification or proof material.
```

For ZET, private archive data must remain private:

- private zet,
- source/original objet,
- local relationship graph,
- AI conversation records,
- body content,
- private receipts or review details.

A future public proof layer may eventually contain only minimal proof material, such as:

- hashes,
- receipt references,
- delegation/share proof references,
- attestation proof references,
- revocation pointers.

DID-compatible identity may be future research. This batch does not implement DID, wallet, key custody, chain registry, validator governance, system token, or public proof anchoring.

## v0.3.0 Non-Goals

Even if v0.3.0 starts with one approved receiver-side write, the first boundary should still avoid:

- real ZET transport,
- key generation,
- key-sharing registry,
- radio-frequency access creation,
- mirroring delivery,
- automatic feed update,
- provider sync,
- projection writes,
- WordPress publishing,
- trust graph mutation,
- anchor or apply behavior,
- public proof anchoring,
- token mechanics,
- payment or staking,
- model training,
- full-auto execution.

The next line should stay small enough that a human can inspect it and understand what changed.

## v0.3.0 Boundary Realization

v0.3.0 opens only this write:

```text
archive shared-update-attestation-review
```

It reuses `zet_shared_update_record_review_preview`, requires `--approve` and `--reviewed-by`, writes exactly one local review record and one matching receipt, refuses overwrite/replay, and rolls back the record if the receipt write fails.

This is still not real ZET transport, trust graph mutation, import, acceptance, signature, anchor/apply, public proof, provider sync, projection, feed update, queue/worker, DID/wallet/key custody, payment/staking/consensus/blockchain/token behavior, model training, backpropagation, or full-auto execution.
