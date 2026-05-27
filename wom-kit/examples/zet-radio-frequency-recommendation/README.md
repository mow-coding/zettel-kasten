# ZET Radio-Frequency Recommendation Example

This folder contains sanitized, non-executable examples for the v0.2.48 ZET radio-frequency recommendation model baseline.

The examples show future metadata shape only. They do not fetch content, rank feeds, call providers, update neighbor feeds, publish to a surface, write receipts, run real ZET transport, train models, or create trust/import/attestation/signature/minting state.

Use these examples as design placeholders for the distinction between:

- followed/neighbor feed from explicit relationships,
- recommended/broadcast feed from user/node-owned selector logic.

The selector is inspectable by design and keeps `central_black_box_ranking_used` false.
