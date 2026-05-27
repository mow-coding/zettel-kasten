# Work Log: Public Release Link Hygiene

Date: 2026-05-27
Release: v0.2.49

## Goal

Add a local guardrail so repository release notes do not contain links that work locally but break when copied into GitHub Release bodies.

## What Changed

- Added `wom-kit/tools/check_public_links.py`.
- Added unit tests for local Markdown link resolution, release-note link restrictions, GitHub `blob` links, and suspicious GitHub `tree` file links.
- Fixed known unsafe release-note relative file links.
- Added public documentation explaining repo-local links versus GitHub Release body links.
- Updated release/version bookkeeping to v0.2.49.

## Safety Boundary

This batch added a development validation script only. It did not add archive product behavior, provider calls, GitHub Release editing, network URL fetching, trust/import/attestation/signature writes, ZET transport, projection writes, recommendation ranking, or feed updates.

## Verification Plan

- Run the full unit test suite.
- Run strict doctor through both wrapper and package entrypoints.
- Run the public link checker.
- Run diff whitespace, naming, privacy, network/provider behavior, and trust-boundary scans.

