# Work Log: v0.2.51 Korean Product Language Hygiene Checker

Date: 2026-05-27
Status: public-safe work log

## Goal

Add a local deterministic checker that helps prevent accidental drift from the v0.2.50 Korean product-language baseline.

## What Changed

- Added `wom-kit/tools/check_korean_product_language.py`.
- Added `wom-kit/tests/test_korean_product_language_hygiene.py`.
- Added `wom-kit/docs/korean-product-language-hygiene.md`.
- Added `wom-kit/docs/releases/v0.2.51.md`.
- Updated release/version bookkeeping to `0.2.51`.

## Checker Scope

The checker reads tracked and untracked public Markdown files reported by Git. It skips ignored private records such as meeting minutes and local decision logs.

It validates the baseline anchors in `wom-kit/docs/concepts/korean-product-language-baseline.ko.md` and flags a small set of high-risk public wording regressions.

## Safety Boundary

The checker is local-only and read-only. It does not edit files, fetch external URLs, call providers, add product CLI commands, add MCP tools, run ZET transport, create trust/import/acceptance/anchor, create attestation/signature writes, publish to WordPress, run recommendation fetching/ranking/feed updates, add workers, train models, or enable full-auto behavior.

## Verification Plan

- Run unit tests.
- Run strict doctor through both CLI entrypoints.
- Run public link hygiene.
- Run Korean product-language hygiene.
- Run whitespace, naming, privacy, code-only, and boundary scans.
