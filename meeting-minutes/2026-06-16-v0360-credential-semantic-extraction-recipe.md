# 2026-06-16 v0.3.60 Credential Semantic Extraction Recipe

## Context

Recent field feedback kept pointing at a practical beginner problem: people may
already have passwords, API keys, mail app passwords, SSO notes, recovery
codes, and status notes mixed together in old plaintext notes. A safe WOM flow
must not tell AI to read or import those values directly.

## Decision

Add a read-only `credential-semantic-extraction-recipe` command before the
existing plaintext migration plan.

The command returns a recipe for human review. It names possible entry classes,
human questions, classification rules, output shape, privacy guards, and closed
actions. It requires a safe `--source-label` and `--dry-run`.

## Safety Boundary

The command reads no plaintext file, opens no password manager/keyring/browser
store, reads no environment variables, detects no secret values, writes no
files, calls no providers, and returns no secret values to AI.

It is not a secret scanner or importer. It only helps a human and AI decide how
to split a complex note before a later one-candidate-at-a-time migration plan.
