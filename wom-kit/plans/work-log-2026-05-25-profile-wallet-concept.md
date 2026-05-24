# Work Log: v0.2.25 Profile Wallet Concept

Date: 2026-05-25

## Intent

Record the product/philosophy shift that a WOM profile should feel closer to a wallet identity than a SaaS account profile.

The comparison is conceptual:

```text
MetaMask wallet = address + private key + signing authority + dApp identity
WOM profile     = node identity + archive access identity + future signing/capability identity + ZET interaction identity
```

## Implemented

- Added read-only CLI `profile-wallet`.
- Added read-only MCP `wom_profile_wallet_check`.
- Added optional `node` and `wallet` profile registry metadata.
- Added safe placeholder profile registry example.
- Added profile wallet model and release documentation.
- Kept existing `profile-list` and `profile-resolve` compatible.

## Safety Decisions

- No private key generation.
- No real cryptographic signing.
- No seed phrase, private key, token, or wallet secret storage.
- No blockchain/provider API calls.
- No wallet apply/register/sign MCP tool.
- Profile wallet output is a readiness preview, not authority.

## Future Work

Real wallet/key custody needs separate design for recovery, hardware wallets, multisig, OS keychain integration, threat modeling, and human approval UX.
