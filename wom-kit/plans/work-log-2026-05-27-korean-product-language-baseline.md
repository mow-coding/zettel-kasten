# Work Log: v0.2.50 Korean Product Language Baseline

Date: 2026-05-27
Status: public-safe work log

## Goal

Record a compact Korean product-language baseline for WOM without changing CLI, MCP, schemas, filenames, or implementation identifiers.

## What Changed

- Added `wom-kit/docs/concepts/korean-product-language-baseline.ko.md`.
- Added `wom-kit/docs/releases/v0.2.50.md`.
- Updated README and public documentation maps to point to the Korean product-language baseline.
- Updated version metadata from `0.2.49` to `0.2.50`.

## Product-Language Decisions Captured

- `WOM` is pronounced `옴`.
- `zet` may be explained as `쪽글` or `토막글`, but remains `zet`.
- `ZET` may be explained as `공유 계층`, but remains `ZET`.
- `objet` is `오브제`.
- `mint -> 발행`, `delegate -> 공유`, `attest -> 수용`, `anchor -> 반영`, and `attest + anchor -> 갱신`.
- `foreign block -> 소포`, `quarantine -> 검문소`, `trust -> 인증`, `import -> 반입`, and `acceptance -> 채택`.
- `block -> 상자`, `header -> 초록`, and `body -> 본문`.
- `radio-frequency -> 라디오 주파수 방식`, `key-sharing -> 키 방식`, and `mirroring -> 미러링 방식`.
- `projection -> 구현`, `surface -> 수제 앱`, and `prompt-as-algorithm -> 수제 알고리즘`.
- `neighbor -> 이웃`, `feed -> 담벼락`, `broadcast -> 송출`, `receipt -> 영수증`, `provenance -> 족보`, `canonical -> 정본`, and `node -> 노드`.
- SNS-type ZET phrases: `젯 갱신하기` and `쿠키 굽기`.
- Messenger-type ZET thread spelling: `스레드`.

## Safety Boundary

This batch is documentation-only. It adds no product CLI/MCP commands and opens no real ZET transport, trust/import/acceptance/anchor, RF access, key-sharing registry, mirroring delivery, provider sync, WordPress publishing, projection write, recommendation fetching/ranking/feed update, attestation/signature write, blockchain/economic layer, model training, or full-auto behavior.

## Verification Plan

- Run unit tests.
- Run strict doctor on the fake archive through both CLI entrypoints.
- Run public link hygiene checker.
- Run whitespace, naming, and privacy scans.
