# Next Thread Prompt: ZET Sharing Lifecycle Terminology

Use this prompt when continuing the next design/implementation batch.

## Context

The project has stabilized private minting:

```text
draft zet -> mint-zettel -> canonical private zet -> mint receipt -> draft snapshot
```

The next conceptual layer is future `zet` sharing.

The user does not want ordinary SaaS verbs such as download, share, receive, or save to define the core philosophy.

The preferred terminology candidate is:

```text
mint -> delegate -> attest -> anchor
```

## Current Meaning

- `mint`: issue a `zet` as canonical private archive memory.
- `delegate`: give a scoped capability around a minted `zet` to a specific subject, archive, agent, group, or workspace.
- `attest`: verify a foreign delegated `zet` and record evidence of its issuer, hash, protocol/schema profile, and delegated condition.
- `anchor`: place an attested foreign `zet` into the recipient archive's meaning network while preserving foreign provenance.

## Important Distinctions

- `attest` is not liking, agreeing, endorsing, reposting, or adopting.
- `delegate` is not ownership transfer.
- `anchor` is not simply saving a file.
- Same app version is not the right compatibility model.

Use:

```text
protocol compatibility
schema compatibility
trust profile compatibility
capability compatibility
```

## Next Good Planning Target

Design a dry-run-only `zet` sharing intake model around:

- delegate receipt,
- attestation receipt,
- anchor metadata,
- trust gate,
- capability gate,
- no real P2P/SNS/feed implementation yet.
