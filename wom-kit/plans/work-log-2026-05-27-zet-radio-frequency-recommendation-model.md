# Work Log: ZET Radio-Frequency Recommendation Model

Date: 2026-05-27
Release: v0.2.48

## Goal

Record a public baseline for future ZET recommendation behavior before any feed/ranking implementation exists.

## What Changed

- Added the ZET radio-frequency recommendation model document.
- Added a sanitized non-executable selector shape example.
- Updated public navigation, release history, version metadata, and safety notes.

## Design Notes

The model separates:

- followed/neighbor feed: explicit relationships, delegates, groups, and permission graph,
- recommended/broadcast feed: user/node-owned selector logic that should be inspectable, configurable, and explainable.

The radio-frequency metaphor means a node chooses a ZET channel or scope to tune. It is product language only; it is not a hardware, provider, relay, or real transport feature in v0.2.48.

Prompt-as-algorithm is broader than an LLM prompt. It may later mean a rule bundle, config, code policy, or signed selector artifact.

## Non-Implementation Boundary

This batch intentionally did not add CLI commands, MCP tools, schemas, provider calls, feed updates, ranking, transport, trust, attestation, minting, projection writes, receipts, or background workers.

## Verification Plan

- Run the full WOM-kit unit test suite.
- Run strict doctor through both wrapper and package entrypoints.
- Run diff whitespace checks.
- Run naming and privacy scans.
- Validate the example JSON parses and keeps action flags disabled.
