# WOM Profile Wallet Model

Status: v0.2.25 concept baseline

## Purpose

A WOM profile should not behave like a boring SaaS account profile forever.

The long-term model is closer to a wallet identity:

```text
MetaMask wallet = address + private key + signing authority + dApp identity
WOM profile     = node identity + archive access identity + future signing/capability identity + ZET interaction identity
```

v0.2.25 does not turn a WOM profile into a crypto wallet. It records a wallet-ready identity model and adds read-only previews.

## Model

```text
WOM profile
= human-facing selectable profile

WOM node
= subject/principal in the WOM network

WOM wallet layer
= future signing/capability layer for mint, delegate, attest, anchor, receipts, block headers, and ZET sharing
```

The same shape can describe a person, organization, team, family, project, or future AI-agent node.

## Optional Registry Fields

Profile registry entries may include public-safe metadata:

```yaml
node:
  node_id: node:person:example
  node_kind: person
  display_label: Example Person

wallet:
  wallet_id: wallet:local:example
  fingerprint: wom-fp-example
  custody: local_device
  signing_status: placeholder
  signer_ref: signer:local-placeholder
```

These fields are optional. Existing registry entries remain valid.

## Safety Boundary

The fields above are metadata only.

They must not contain:

- private keys,
- seed phrases,
- wallet secrets,
- raw token values,
- payment credentials,
- real wallet addresses,
- provider URLs with credentials,
- local absolute paths,
- raw OAuth refresh tokens,
- cookies or password values.

## Preview Command

```bash
archive profile-wallet <archive-root> --profile <profile-id-or-label> --dry-run --format json
```

The command reads an existing profile registry, resolves the requested profile, and returns:

- `profile`,
- `node_identity_preview`,
- `wallet_identity_preview`,
- `signing_readiness`,
- `capability_surface_preview`,
- `blockers`,
- `warnings`,
- `would_change: []`.

It writes nothing, generates no keys, signs nothing, calls no blockchain APIs, and calls no provider APIs.

MCP exposes only:

```text
wom_profile_wallet_check
```

There is no wallet apply/register/sign tool in v0.2.25.

## Future Direction

The wallet layer can later become the place where a profile proves authority for:

- mint,
- delegate,
- attest,
- anchor,
- receipts,
- block headers,
- ZET sharing.

That future work needs careful private-key custody, recovery, UX, hardware wallet, multisig, and threat-model design. v0.2.25 intentionally defers it.
