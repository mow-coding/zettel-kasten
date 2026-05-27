# Korean Product Language Hygiene

Status: v0.2.51 local documentation guardrail
Date: 2026-05-27

v0.2.51 adds a small local checker for the Korean product-language baseline.

The checker protects [Korean Product Language Baseline](concepts/korean-product-language-baseline.ko.md) from accidental drift. It is intentionally simple: it reads public Markdown files known to Git, verifies that the baseline document still contains the required anchors, and catches a few high-risk current-facing wording regressions.

Run it from the repository root:

```powershell
python wom-kit\tools\check_korean_product_language.py
```

## What It Checks

The checker verifies that the baseline still preserves anchors such as:

- `WOM -> 옴`,
- `zettel-kasten -> 기록 계층`,
- `zet -> 쪽글` or `토막글`,
- `ZET -> 공유 계층`,
- `objet -> 오브제`,
- `mint -> 발행`,
- `delegate -> 공유`,
- `attest -> 수용`,
- `anchor -> 반영`,
- `foreign block -> 소포`,
- `quarantine -> 검문소`,
- `block -> 상자`,
- `header -> 초록`,
- `projection -> 구현`,
- `surface -> 수제 앱`,
- `prompt-as-algorithm -> 수제 알고리즘`,
- `젯 갱신하기`,
- `쿠키 굽기`,
- `스레드`.

It also guards against a few risky phrases:

- using the wrong Korean pronunciation for `WOM`,
- drifting the tagline away from `인간 인식의 지평`,
- using current-facing spellings such as mixed-case WOM or capitalized zet forms,
- describing messenger reply chains as blockchain or public-ledger technology,
- turning a borrowed surface example into the primary WOM/ZET interface or transport layer.

## What It Is Not

This checker is not a translation engine.

It does not rewrite files automatically. It does not rename code identifiers, CLI commands, JSON fields, schema fields, filenames, or Python identifiers. It does not fetch external URLs, call providers, inspect private archives, or use a language model.

## Safety Boundary

This release does not implement UI, real ZET transport, RF access, key-sharing registry, mirroring delivery, real trust/import/acceptance/anchor, attestation/signature writes, provider sync, WordPress publishing, projection writes, recommendation fetching/ranking/feed updates, Redis, queues, background workers, payments, staking, consensus, blockchain, model training, backpropagation, or full-auto behavior.
